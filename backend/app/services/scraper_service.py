import uuid
import re
import html
from datetime import datetime, timedelta, timezone
import httpx
from bs4 import BeautifulSoup
from app.models import db, Activity
from app.services.geo_service import GeoService

class KvikmyndirScraper:
    def __init__(self):
        self.target_url = "https://kvikmyndir.is/bio/syningatimar/?dagur=0"
        self.base_url = "https://kvikmyndir.is"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "is,en-US;q=0.7,en;q=0.3"
        }

    async def execute(self):
        """Main execution method to fetch and parse movie data."""
        async with httpx.AsyncClient(follow_redirects=True, headers=self.headers) as client:
            response = await client.get(self.target_url, timeout=10.0)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            movie_blocks = soup.find_all('div', class_=re.compile(r'\bstimar\b'))

            for movie in movie_blocks:
                await self._process_movie_block(movie, client)

    async def _process_movie_block(self, movie, client):
        """Handles the extraction logic for a single movie block."""
        title_node = movie.select_one('.movie_title .title')
        if not title_node:
            return
            
        title = title_node.contents[0].strip()
        movie_id, image_url = self._extract_id_and_image(movie)
        
        booking_links = await self._fetch_booking_links(movie_id, client) if movie_id else {}
        
        trivia_node = movie.select_one('.st-trivia')
        description = trivia_node.get_text(strip=True) if trivia_node else "No description available."

        meta_node = movie.select_one('.st-meta')
        category = meta_node.get_text(strip=True).split('·')[0].strip() if meta_node else 'misc'

        for showtime in movie.select('a.st-showtime-link'):
            await self._save_showtime(showtime, title, description, category, image_url, booking_links, client)

    def _extract_id_and_image(self, movie):
        movie_id, image_url = None, None
        image_anchor = movie.select_one('a[href^="/mynd/?id="]')
        if image_anchor:
            id_match = re.search(r'\?id=(\d+)', image_anchor.get('href', ''))
            if id_match:
                movie_id = id_match.group(1)
            img_node = image_anchor.find('img')
            if img_node and img_node.get('src'):
                src = img_node.get('src')
                image_url = self.base_url + src if src.startswith('/') else src
        return movie_id, image_url

    async def _fetch_booking_links(self, movie_id, client):
        links = {}
        try:
            res = await client.get(f"{self.base_url}/mynd/?id={movie_id}", timeout=10.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                showtimes = soup.select('.mp-showtimes__day[data-date="0"] a.st-showtime-link')
                for st_link in showtimes:
                    cinema, time_str, href = st_link.get('data-cinema'), st_link.get('data-time'), st_link.get('href')
                    if cinema and time_str and href and href != "#":
                        links[(cinema, time_str.replace('.', ':'))] = href
        except httpx.RequestError as e:
            print(f"Could not fetch ticket links for movie {movie_id}: {e}")
        return links

    async def _save_showtime(self, showtime, title, description, category, image_url, booking_links, client):
        start_time_str = showtime.get('data-showtime')
        if not start_time_str:
            return
            
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        cinema = showtime.get('data-cinema', 'Unknown Cinema')
        
        source_url = booking_links.get((cinema, start_time.strftime('%H:%M')))
        final_price = await self._extract_price(source_url, client) if source_url else None
        
        end_time = start_time + timedelta(hours=2)
        parent_li = showtime.find_parent('li')
        if parent_li and parent_li.get('data-tip'):
            match = re.search(r'Búin kl\. ~(\d{2}):(\d{2})', parent_li.get('data-tip'))
            if match:
                end_time = start_time.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0)
                if end_time < start_time:
                    end_time += timedelta(days=1)

        coord_list = GeoService.find_coords_by_name(cinema)

        activity = Activity(
            id=str(uuid.uuid4()),
            title=f"{title} ({cinema})"[:255], 
            description=description,
            category=category,
            price=final_price,
            start_time=start_time,
            end_time=end_time,
            image_url=image_url,
            source_url=source_url,
            lat=coord_list[0],
            lon=coord_list[1]
        )
        db.session.add(activity)
        db.session.commit()

    async def _extract_price(self, source_url, client):
        try:
            res = await client.get(source_url, timeout=15.0)
            if res.status_code != 200:
                return None
                
            html_text = html.unescape(res.text)
            patterns = [
                re.compile(r'(\d{1,2}[.,]\d{3}|\d{3,5})\s*(?:&nbsp;)?\s*(?:kr\.?|isk|íkr)', re.IGNORECASE),
                re.compile(r'(?:data-)?ticketprice["\']?\s*[:=]\s*["\']?(\d{3,5}(?:\.\d+)?)', re.IGNORECASE),
                re.compile(r'ver[ðd][^0-9]{1,10}(\d{1,2}[.,]\d{3}|\d{3,5})', re.IGNORECASE)
            ]
            
            found_prices = []
            for pattern in patterns:
                for match in pattern.findall(html_text):
                    try:
                        found_prices.append(int(float(match.replace('.', '').replace(',', '')))) 
                    except ValueError:
                        pass
                        
            valid_prices = [p for p in found_prices if 500 <= p <= 5000]
            return min(valid_prices) if valid_prices else None
        except httpx.RequestError:
            return None
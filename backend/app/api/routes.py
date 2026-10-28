from flask import Blueprint, jsonify, request, render_template_string
from datetime import datetime, timezone
from app.models import db, Activity
from app.services.geo_service import GeoService
from app.services.scraper_service import KvikmyndirScraper

api_bp = Blueprint('api', __name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Activity Feed & Map</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Leaflet CSS & JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="bg-gray-100 text-gray-900 font-sans">

    <header class="sticky top-0 bg-white shadow-sm z-50 p-4">
        <div class="flex justify-between items-center mb-3">
            <h1 class="text-xl font-bold text-center">What's Happening Today</h1>
            <!-- View Switcher Tabs -->
            <div class="flex bg-gray-200 rounded-full p-1 text-xs font-semibold">
                <button onclick="switchView('feed')" id="btn-feed" class="px-3 py-1 bg-white shadow rounded-full text-blue-600 transition">Feed</button>
                <button onclick="switchView('map')" id="btn-map" class="px-3 py-1 text-gray-600 transition">Map</button>
            </div>
        </div>

        <div class="flex space-x-2 overflow-x-auto no-scrollbar pb-1" id="category-filters">
            <button onclick="fetchFeed('all')" class="px-4 py-2 bg-blue-600 text-white rounded-full font-medium whitespace-nowrap">All</button>
            <button onclick="fetchFeed('movie')" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-full font-medium whitespace-nowrap">Movies</button>
            <button onclick="fetchFeed('food')" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-full font-medium whitespace-nowrap">Food</button>
            <button onclick="fetchFeed('misc')" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-full font-medium whitespace-nowrap">Misc</button>
        </div>
    </header>

    <!-- Main Content Containers -->
    <main class="p-4">
        <!-- Feed View -->
        <div id="feed-container" class="space-y-6">
            <p class="text-center text-gray-500 mt-10">Requesting location...</p>
        </div>

        <!-- Map View -->
        <div id="map-container" class="hidden h-[75vh] w-full rounded-2xl shadow-md overflow-hidden relative">
            <div id="map" class="h-full w-full z-10"></div>
        </div>
    </main>

    <script>
        // Fallback user location (Reykjavík center) if geolocation is denied
        let USER_LAT = 64.1466;
        let USER_LON = -21.9426;
        let currentCategory = 'all';
        let currentActivities = [];
        
        let map = null;
        let markersLayer = null;

        // 1. Initialize app by asking for location
        function initApp() {
            if ("geolocation" in navigator) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        USER_LAT = position.coords.latitude;
                        USER_LON = position.coords.longitude;
                        fetchFeed(currentCategory);
                    },
                    (error) => {
                        console.warn("Geolocation denied or failed. Using default Reykjavík coordinates.");
                        fetchFeed(currentCategory);
                    }
                );
            } else {
                fetchFeed(currentCategory);
            }
        }

        // 2. View Switcher Logic
        function switchView(view) {
            const feedContainer = document.getElementById('feed-container');
            const mapContainer = document.getElementById('map-container');
            const btnFeed = document.getElementById('btn-feed');
            const btnMap = document.getElementById('btn-map');

            if (view === 'feed') {
                feedContainer.classList.remove('hidden');
                mapContainer.classList.add('hidden');
                btnFeed.className = "px-3 py-1 bg-white shadow rounded-full text-blue-600 transition";
                btnMap.className = "px-3 py-1 text-gray-600 transition";
            } else {
                feedContainer.classList.add('hidden');
                mapContainer.classList.remove('hidden');
                btnFeed.className = "px-3 py-1 text-gray-600 transition";
                btnMap.className = "px-3 py-1 bg-white shadow rounded-full text-blue-600 transition";
                
                // Initialize map and refresh size once visible
                initMap();
                updateMapMarkers(currentActivities);
            }
        }

        // 3. Initialize Leaflet Map
        function initMap() {
            if (!map) {
                map = L.map('map').setView([USER_LAT, USER_LON], 13);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '© OpenStreetMap contributors'
                }).addTo(map);
                markersLayer = L.layerGroup().addTo(map);
            } else {
                map.invalidateSize();
            }
        }

        // 4. Update Map Markers
        function updateMapMarkers(activities) {
            if (!map || !markersLayer) return;
            markersLayer.clearLayers();

            // Add user location marker
            const userMarker = L.circleMarker([USER_LAT, USER_LON], {
                radius: 9,
                fillColor: '#3b82f6',
                color: '#ffffff',
                weight: 3,
                fillOpacity: 1
            }).bindPopup("<b>You are here</b>");
            markersLayer.addLayer(userMarker);

            // Add activity markers
            activities.forEach(activity => {
                if (activity.lat && activity.lon) {
                    const formatTime = (isoString) => isoString ? new Date(isoString).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                    const startTimeStr = formatTime(activity.start_time) || 'Anytime';
                    const targetUrl = activity.source_url ? activity.source_url : '#';
                    
                    const popupContent = `
                        <div class="p-1 space-y-1">
                            <span class="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 bg-gray-100 rounded text-gray-600">${activity.category}</span>
                            <h3 class="font-bold text-sm leading-tight">${activity.title}</h3>
                            <p class="text-xs text-blue-600 font-bold">${activity.price ? activity.price + ' ISK' : 'Free'}</p>
                            <p class="text-xs text-gray-500">${startTimeStr} ${activity.distance_km ? '• ' + activity.distance_km + ' km' : ''}</p>
                            <div class="pt-1">
                                <a href="${targetUrl}" target="_blank" class="inline-block bg-black text-white px-3 py-1 rounded text-xs font-medium">Book Now</a>
                            </div>
                        </div>
                    `;

                    const marker = L.marker([activity.lat, activity.lon]).bindPopup(popupContent);
                    markersLayer.addLayer(marker);
                }
            });
        }

        async function fetchFeed(category = 'all') {
            currentCategory = category;
            const feedContainer = document.getElementById('feed-container');
            feedContainer.innerHTML = '<p class="text-center text-gray-500 mt-10">Loading activities...</p>';

            try {
                const response = await fetch(`/api/feed?category=${category}&lat=${USER_LAT}&lon=${USER_LON}`);
                const data = await response.json();
                
                if (data.status === 'success') {
                    currentActivities = data.data;
                    renderCards(currentActivities);
                    if (map) {
                        updateMapMarkers(currentActivities);
                    }
                } else {
                    feedContainer.innerHTML = '<p class="text-center text-red-500 mt-10">Failed to load feed.</p>';
                }
            } catch (error) {
                console.error("Error fetching feed:", error);
                feedContainer.innerHTML = '<p class="text-center text-red-500 mt-10">Network error.</p>';
            }
        }

        function renderCards(activities) {
            const feedContainer = document.getElementById('feed-container');
            feedContainer.innerHTML = ''; 

            if (activities.length === 0) {
                feedContainer.innerHTML = `
                    <div class="text-center mt-10">
                        <p class="text-gray-500 mb-4">No activities found.</p>
                        <button onclick="triggerScraper()" class="px-4 py-2 bg-green-500 text-white rounded shadow">Trigger Scraper to Add Data</button>
                    </div>`;
                return;
            }

            activities.forEach(activity => {
                const formatTime = (isoString) => isoString ? new Date(isoString).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                const startTimeStr = formatTime(activity.start_time) || 'Anytime';
                const endTimeStr = formatTime(activity.end_time);
                const timeDisplay = endTimeStr ? `${startTimeStr} - ${endTimeStr}` : startTimeStr;
                
                const targetUrl = activity.source_url ? activity.source_url : '#';
                const imageDiv = activity.image_url 
                    ? `<img src="${activity.image_url}" alt="${activity.title}" class="w-full h-full object-cover transition-transform duration-300 hover:scale-105">` 
                    : `<div class="w-full h-full flex items-center justify-center text-gray-500">No Image</div>`;

                let displayTitle = activity.title;
                if (activity.distance_km !== null) {
                    if (displayTitle.endsWith(')')) {
                        displayTitle = displayTitle.slice(0, -1) + ` - ${activity.distance_km} km)`;
                    } else {
                        displayTitle += ` (${activity.distance_km} km)`;
                    }
                }

                const cardHTML = `
                    <div class="bg-white rounded-2xl shadow-md overflow-hidden flex flex-col h-[60vh] max-h-[600px]">
                        <a href="${targetUrl}" target="_blank" class="h-1/2 bg-gray-300 relative block overflow-hidden">
                            ${imageDiv}
                            <span class="absolute top-3 left-3 bg-white/90 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider text-gray-700">
                                ${activity.category}
                            </span>
                        </a>
                        
                        <div class="p-5 flex-1 flex flex-col justify-between">
                            <div class="overflow-hidden">
                                <div class="flex justify-between items-start mb-2">
                                    <h2 class="text-2xl font-bold leading-tight line-clamp-2">${displayTitle}</h2>
                                    <span class="text-lg font-bold text-blue-600 whitespace-nowrap ml-3">${activity.price} ISK</span>
                                </div>
                                <p class="text-gray-600 line-clamp-3 text-sm">${activity.description || 'No description available.'}</p>
                            </div>
                            
                            <div class="mt-4 flex items-center justify-between text-sm text-gray-500">
                                <span class="flex items-center font-medium">
                                    <svg class="w-4 h-4 mr-1 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                    ${timeDisplay}
                                </span>
                                <a href="${targetUrl}" target="_blank" class="bg-black hover:bg-gray-800 text-white px-5 py-2 rounded-lg font-medium transition-colors">
                                    Book Now
                                </a>
                            </div>
                        </div>
                    </div>
                `;
                feedContainer.innerHTML += cardHTML;
            });
        }

        async function triggerScraper() {
            try {
                await fetch('/api/admin/trigger-scrape', { method: 'POST' });
                alert('Data scraped and added! Refreshing feed...');
                fetchFeed(currentCategory);
            } catch(e) {
                alert('Scraping failed.');
            }
        }

        window.onload = initApp;
    </script>
</body>
</html>
"""

@api_bp.route('/', methods=['GET'])
def index():
    """Serves the test UI."""
    return render_template_string(HTML_TEMPLATE)

@api_bp.route('/feed', methods=['GET'])
def get_feed():
    """Returns the feed data and calculates distance if user_lat/user_lon provided."""
    category_filter = request.args.get('category')
    user_lat = request.args.get('lat')
    user_lon = request.args.get('lon')
    now = datetime.now(timezone.utc)
    
    query = Activity.query.filter(Activity.end_time > now)
    
    if category_filter and category_filter.lower() != 'all':
        query = query.filter(Activity.category == category_filter.lower())
        
    # Example to fetch closest first (if location is provided) or fallback to time
    activities = query.order_by(Activity.start_time.asc()).limit(50).all()
    
    output_data = []
    for activity in activities:
        act_dict = activity.to_dict()
        if user_lat and user_lon and act_dict.get('lat') and act_dict.get('lon'):
            act_dict['distance_km'] = GeoService.calculate_distance_km(
                user_lat, user_lon, act_dict['lat'], act_dict['lon']
            )
        else:
            act_dict['distance_km'] = None
        output_data.append(act_dict)

    # Optional: If you want to sort by distance instead of time when location is given
    if user_lat and user_lon:
        output_data.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else float('inf'))

    return jsonify({
        "status": "success",
        "count": len(output_data),
        "data": output_data
    })

@api_bp.route('/admin/trigger-scrape', methods=['POST'])
async def trigger_scrape():
    """API endpoint that triggers the Kvikmyndir web scraper."""
    try:
        scraper = KvikmyndirScraper()
        await scraper.execute()
        return jsonify({"status": "success", "message": "Data scraped and saved to DB"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
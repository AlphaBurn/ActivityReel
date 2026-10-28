import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from app.models import db, Location

class GeoService:
    @staticmethod
    def calculate_distance_km(user_lat, user_lon, event_lat, event_lon):
        if None in (user_lat, user_lon, event_lat, event_lon):
            return None
        try:
            user_coords = (float(user_lat), float(user_lon))
            event_coords = (float(event_lat), float(event_lon))
            return round(geodesic(user_coords, event_coords).kilometers, 1)
        except ValueError:
            return None

    @staticmethod
    def find_coords_by_name(place):
        existing_loc = Location.query.get(place)
        if existing_loc and existing_loc.lat and existing_loc.lon:
            return [float(existing_loc.lat), float(existing_loc.lon)]

        geolocator = Nominatim(user_agent="iceland_activity_aggregator")
        try:
            location = geolocator.geocode(place)
            time.sleep(1.1) 
            if location:
                print(f"Geocoded and saving to DB: {location.address}")
                new_loc = Location(name=place, lat=location.latitude, lon=location.longitude)
                db.session.add(new_loc)
                db.session.commit()
                return [location.latitude, location.longitude]
        except Exception as e:
            print(f"Geocoding error for {place}: {e}")
        
        return [None, None]
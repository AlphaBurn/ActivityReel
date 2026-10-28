from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.String(36), primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    price = db.Column(db.Integer, default=0)
    discounted_price = db.Column(db.Integer)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    lat = db.Column(db.Numeric(9, 6))
    lon = db.Column(db.Numeric(9, 6))
    category = db.Column(db.String(50), nullable=False)
    source_url = db.Column(db.String(512))
    metadata_data = db.Column('metadata', db.JSON, default={})
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "discounted_price": self.discounted_price,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "category": self.category,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "lat": float(self.lat) if self.lat else None,
            "lon": float(self.lon) if self.lon else None
        }

class Location(db.Model):
    __tablename__ = 'locations'

    name = db.Column(db.String(255), primary_key=True)
    lat = db.Column(db.Numeric(9, 6))
    lon = db.Column(db.Numeric(9, 6))
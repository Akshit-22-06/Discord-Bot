import json
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import DATABASE_URL

if DATABASE_URL:
    db_url = DATABASE_URL
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://' which many cloud providers use.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)
else:
    engine = create_engine('sqlite:///database/mafia.db')

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Game(Base):
    __tablename__ = 'games'
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer)
    winner = Column(String)
    num_players = Column(Integer)
    story_log = Column(Text)

class Movie(Base):
    __tablename__ = 'movies'
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)
    title = Column(String)
    added_by = Column(String)
    votes = Column(Integer, default=1)

def init_db():
    Base.metadata.create_all(engine)

def save_game(channel_id: int, winner: str, num_players: int, story_log: list[str]):
    session = SessionLocal()
    new_game = Game(channel_id=channel_id, winner=winner, num_players=num_players, story_log=json.dumps(story_log))
    session.add(new_game)
    session.commit()
    session.close()

def get_past_stories():
    session = SessionLocal()
    games = session.query(Game).order_by(Game.id.desc()).limit(5).all()
    stories = [json.loads(g.story_log) for g in games]
    session.close()
    return stories

def add_movie(guild_id: int, title: str, added_by: str):
    session = SessionLocal()
    # Case-insensitive search for existing movie
    existing_movie = session.query(Movie).filter(Movie.guild_id == guild_id, Movie.title.ilike(title)).first()
    
    if existing_movie:
        existing_movie.votes += 1
    else:
        new_movie = Movie(guild_id=guild_id, title=title, added_by=added_by, votes=1)
        session.add(new_movie)
        
    session.commit()
    session.close()

def get_movies(guild_id: int):
    session = SessionLocal()
    movies = session.query(Movie).filter_by(guild_id=guild_id).all()
    result = [{"id": m.id, "title": m.title, "added_by": m.added_by, "votes": m.votes} for m in movies]
    session.close()
    return result

def clear_movies(guild_id: int):
    session = SessionLocal()
    session.query(Movie).filter_by(guild_id=guild_id).delete()
    session.commit()
    session.close()

def remove_movie(movie_id: int):
    session = SessionLocal()
    session.query(Movie).filter_by(id=movie_id).delete()
    session.commit()
    session.close()

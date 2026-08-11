# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy.ext.declarative import declarative_base
#
#
# # SQLALCHEMY_DATABASE_URI = "postgresql://postgres:Goodboylucky123@localhost/TodoApplicationDatabase"
# SQLALCHEMY_DATABASE_URI = "sqlite:///./redbasedagric.db"
#
# # engine = create_engine(SQLALCHEMY_DATABASE_URI)
# engine = create_engine(SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})
#
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#
# Base = declarative_base()
#
#
#

from database import engine, Base
import models

'''
print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
'''
print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully.")
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
pepper_data = os.getenv("PEPPER_DATA")

if __name__ == "__main__":
    print(user, password, host, port, db_name, pepper_data)

import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_engine

def inspect_db():
    engine = get_engine()
    print("Testing connection...")
    try:
        with engine.connect() as conn:
            print("Connected! Fetching columns...")
            result = conn.execute(text("DESCRIBE sensor_test_results"))
            columns = result.fetchall()
            for col in columns:
                print(f"Column: {col[0]} | Type: {col[1]} | Null: {col[2]} | Key: {col[3]}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_db()

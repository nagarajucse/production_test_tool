import os
import sys
import openpyxl
import io
from openpyxl.drawing.image import Image as OpenpyxlImage
from PIL import Image as PILImage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_engine
from models import SensorTestResult
from sqlalchemy.orm import Session

def dump_data():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Results"
    headers = ["Date/Time", "Sensor SN", "MAC Address", "Model", "Image Quality", "NFIQ2 Score", "Work Order", "Tester", "Image Format", "Fingerprint Photo"]
    ws.append(headers)
    
    engine = get_engine()
    with Session(engine) as session:
        records = session.query(SensorTestResult).all()
        for record in records:
            row = [
                record.received_at.strftime("%Y-%m-%d %H:%M:%S") if record.received_at else "",
                record.sensor_sn or "",
                record.sensor_mac or "",
                record.model or "",
                record.image_quality if record.image_quality is not None else "",
                record.nfiq2_score if record.nfiq2_score is not None else "",
                record.work_order or "",
                record.tester_id or "",
                record.image_format or ""
            ]
            ws.append(row)
            
            # Add image
            if record.fingerprint_image:
                try:
                    row_idx = ws.max_row
                    img_data = io.BytesIO(record.fingerprint_image)
                    pil_img = PILImage.open(img_data)
                    orig_w, orig_h = pil_img.size
                    ratio = 100.0 / orig_h
                    new_w = int(orig_w * ratio)
                    
                    img_data.seek(0)
                    xl_img = OpenpyxlImage(img_data)
                    xl_img.width = new_w
                    xl_img.height = 100
                    
                    col_letter = "J"
                    cell_ref = f"{col_letter}{row_idx}"
                    ws.add_image(xl_img, cell_ref)
                    
                    ws.row_dimensions[row_idx].height = 80
                    current_w = ws.column_dimensions[col_letter].width
                    if current_w is None or current_w < (new_w / 7.0):
                        ws.column_dimensions[col_letter].width = (new_w / 7.0) + 2
                except Exception as e:
                    print(f"Error adding image: {e}")
    
    # Save to the server directory
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Datasheet.xlsx")
    wb.save(excel_path)
    print(f"Dumped {len(records)} records to {excel_path}")

if __name__ == "__main__":
    dump_data()

import zipfile
import xml.etree.ElementTree as ET
import sys

def get_xlsx_headers(filepath):
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            # 1. Read shared strings
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                xml_content = z.read('xl/sharedStrings.xml')
                root = ET.fromstring(xml_content)
                # namespace usually like {http://schemas.openxmlformats.org/spreadsheetml/2006/main}
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in root.findall('main:si', ns):
                    t = si.find('main:t', ns)
                    if t is not None:
                        shared_strings.append(t.text)
                    else:
                        shared_strings.append("")
            
            # 2. Read sheet1
            sheet_content = z.read('xl/worksheets/sheet1.xml')
            root = ET.fromstring(sheet_content)
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            headers = []
            # Find first row
            sheetData = root.find('main:sheetData', ns)
            if sheetData is not None:
                first_row = sheetData.find('main:row', ns)
                if first_row is not None:
                    for c in first_row.findall('main:c', ns):
                        t_attr = c.get('t')
                        v = c.find('main:v', ns)
                        if v is not None:
                            val = v.text
                            if t_attr == 's': # shared string
                                headers.append(shared_strings[int(val)])
                            else:
                                headers.append(val)
            print("Headers:", headers)
    except Exception as e:
        print("Error reading xlsx:", e)

if __name__ == '__main__':
    get_xlsx_headers(sys.argv[1])

import dataclasses
from pathlib import Path
from typing import Optional, Union
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging

@dataclass
class UploadEntry:
    pack: str
    song: str
    mode: str
    difficulty: str
    timestamp: datetime

def process_upload_xml(contents: ET.ElementTree) -> Union[UploadEntry, str]:
    # note: there can be multiple entries of HighScoreForASongAndSteps (one each for P1 and P2).
    # here we just grab the first one
    node = contents.find('RecentSongScores/HighScoreForASongAndSteps')
    if node is None:
        return "Upload file contained no play information"
    song = node.find('Song')
    song_dir = song.attrib['Dir']
    _, pack, song_name, *_ = song_dir.split('/')
    steps = node.find('Steps')
    difficulty = steps.attrib['Difficulty']
    mode = steps.attrib['StepsType']
    timestamp_raw = node.find('HighScore/DateTime').text
    timestamp = datetime.fromisoformat(timestamp_raw) # datetime.strptime(timestamp_raw, '')
    return UploadEntry(
        pack=pack,
        song=song_name,
        mode=mode,
        difficulty=difficulty,
        timestamp=timestamp
    )

def process_folder(folder_path: Path) -> list[UploadEntry]:
    all_uploads = []
    for xml_file in folder_path.iterdir():
        if xml_file.suffix == ".xml":
            try:
                with open(xml_file, 'r', encoding='utf8', errors='ignore') as f:
                    upload_data = process_upload_xml(ET.parse(f))
                
                if isinstance(upload_data, UploadEntry):
                    all_uploads.append(upload_data)
                else:
                    print(f"Skipping {xml_file}: {upload_data}")
            except Exception as ex:
                raise Exception(f"Error parsing file {xml_file}")  from ex
    return all_uploads
        
# def process_zip(zip_path: Path) -> list[UploadEntry]:
#     return

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        elif isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

def write_data_out(data: list[UploadEntry], out_file: Path) -> None:
    with open(out_file, 'w', encoding='utf8') as f:
        json.dump(data, f, cls=EnhancedJSONEncoder)

def load_data(in_file: Path) -> list[UploadEntry]:
    with open(in_file, 'r', encoding='utf8') as f:
        js = json.load(f)
        return [UploadEntry(**obj) for obj in js]

def load_data(in_file: Path) -> list[UploadEntry]:
    with open(in_file, 'r', encoding='utf8') as f:
        js = json.load(f)
        return pd.DataFrame.from_records(js)

if __name__ == "__main__":
    import sys
    upload_folder = Path(sys.argv[1])
    file_to_write = Path(sys.argv[2])

    write_data_out(process_folder(upload_folder), file_to_write)

    # print(process_upload_xml(ET.parse(path)))



import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

def upload_video(file_path, title, description, tags, privacy_status="private"):
    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27" # 27: 교육 (카테고리에 맞게 수정)
        },
        "status": {
            "privacyStatus": privacy_status, # "public", "private", "unlisted"
            "selfDeclaredMadeForKids": False
        }
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"업로드 완료! 영상 ID: {response['id']}")

if __name__ == "__main__":
    # 클로드가 생성한 결과물과 연동할 부분
    upload_video("output.mp4", "자동 생성 영상 제목", "영상 설명입니다.", ["태그1", "태그2"], "private")

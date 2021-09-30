from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

gauth = GoogleAuth()
# gauth.LocalWebserverAuth()

drive = GoogleDrive(gauth)

# file1 = drive.CreateFile(
#     {"mimeType": "text/toml", "parents": [{"kind": "drive#fileLink", "id": "1E0AKBQwFbICwBoWTK51MntDzH2dE6uXO"}]})
# file1.SetContentFile("pyproject.toml")
# file1.Upload()  # Upload the file.


def create_folder(folder_name):
    folder = drive.CreateFile({"title": folder_name,
                      "mimeType": "application/vnd.google-apps.folder",
                      "parents": [{"kind": "drive#fileLink", "id": "1E0AKBQwFbICwBoWTK51MntDzH2dE6uXO"}]
                      }
                     )
    folder.Upload()
    return folder["id"]

def check_file_exists(file_name):
    fileList = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()

x = check_file_exists("test_upload.txt")
print(x)

# test = create_folder("new")
# print(test)
# def upload_files(files):
#     pass
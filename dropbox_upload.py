import os

import dropbox
from dotenv import load_dotenv

load_dotenv()
dropbox_token = os.getenv("DROPBOX_TOKEN")

print("Initializing Dropbox API...")
dbx = dropbox.Dropbox(dropbox_token)

print("Scanning for expense files...")
result = dbx.files_list_folder(path="")
print(result)
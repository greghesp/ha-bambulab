import glob
import json
import os
import requests
import subprocess

def get_google_translation(to, content):
  sourceLang = 'en'
  targetLang = to
  contentStr = content.strip('"')
  url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sourceLang}&tl={targetLang}&dt=t&q={contentStr}"
  response = requests.get(url)

    # -SessionVariable Session `
    # -UserAgent ([Microsoft.PowerShell.Commands.PSUserAgent]::Chrome) `
    # -Method Get `
    # -ContentType 'application/json'
  
  json = response.json()
  translation = ''
  for result in json[0]:
    translation += result[0]
  translation = translation.replace("\\n", "\n")
  translation = translation.replace("\u003e", ">")
  return translation


def convert(old_source, new_source, target, language):
  for entry in new_source:
    if isinstance(new_source[entry], dict):
      # This is a json node. Recursively process it.
      if not entry in target:
        # Target doesn't have this node yet. Add an empty one.
        target[entry] = {}
      convert(old_source.get(entry, {}), new_source[entry], target[entry], language)
    else:
      # We have a string.
      if (not entry in target) or (old_source[entry] != new_source[entry]):
        # String doesn't exist in the target. Translate it and insert it.
        translation = get_google_translation(language, new_source[entry])
        print(f"{entry} = '{new_source[entry]}' -> '{translation}'")
        target[entry] = translation

  for entry in target.copy():
    if not entry in new_source:
      print(f"Deleting: '{entry}'")
      del target[entry]


# Get the path to the current script file
script_path = os.path.abspath(__file__)
script_path = os.path.dirname(script_path)
sourceDir = os.path.abspath(f"{script_path}/../custom_components/bambu_lab/translations")
englishFile = f"{sourceDir}/en.json"

with open(englishFile, 'r') as file:
  new_english = json.load(file)

result = subprocess.run(['git', 'show', "HEAD:../custom_components/bambu_lab/translations/en.json"], capture_output=True, text=True)
old_english = json.loads(result.stdout)

files = glob.glob(f"{sourceDir}/*.json")
for filepath in files:
  filename = os.path.basename(filepath)
  language = filename.split('.')[0]

  if language == 'en':
    continue
  elif language == 'no-NB':
    language = 'no'
  elif language == 'cz':
    language = 'cs'

  with open(filepath, 'r') as file:
    other_language = json.load(file)

  convert(old_english, new_english, other_language, language)

  with open(filepath, 'w') as file:
    json.dump(other_language, file, ensure_ascii=False, indent=2)

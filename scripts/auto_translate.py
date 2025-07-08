import glob
import json
import os
import sys
import requests
import subprocess
import base64


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
      if (not entry in target) or (not entry in old_source) or (old_source[entry] != new_source[entry]):
        # String doesn't exist in the target. Translate it and insert it.
        translation = get_google_translation(language, new_source[entry])
        print(f"{entry} = '{new_source[entry]}' -> '{translation}'")
        target[entry] = translation

  for entry in target.copy():
    if not entry in new_source:
      print(f"Deleting: '{entry}'")
      del target[entry]


def get_last_release_content():
    # Check if running in GitHub Actions
    if not os.getenv('GITHUB_TOKEN'):
        # Fallback to local git if not in GitHub Actions
        result = subprocess.run(['git', 'show', "HEAD:../custom_components/bambu_lab/translations/en.json"], 
                              capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else '{}'

    # Get repository information from environment
    repo = os.getenv('GITHUB_REPOSITORY', 'greghesp/ha-bambulab')
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }

    # Try to get the latest release first
    releases_url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(releases_url, headers=headers)
    if response.status_code == 200:
        # Release exists, get file from release tag
        tag_name = response.json()['tag_name']
        ref = tag_name
    else:
        # No release found, use default branch
        print("No release found, falling back to default branch")
        ref = 'main'

    # Get the file content
    content_url = f"https://api.github.com/repos/{repo}/contents/custom_components/bambu_lab/translations/en.json?ref={ref}"
    response = requests.get(content_url, headers=headers)
    if response.status_code != 200:
        print("Error: Could not fetch translation file")
        sys.exit(1)

    return base64.b64decode(response.json()['content']).decode('utf-8')

# Get the workspace directory from GitHub environment, fallback to script directory if not available
workspace_dir = os.getenv('GITHUB_WORKSPACE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sourceDir = os.path.normpath(os.path.join(workspace_dir, 'custom_components', 'bambu_lab', 'translations'))
englishFile = os.path.join(sourceDir, 'en.json')

with open(englishFile, 'r') as file:
  new_english = json.load(file)

old_english = json.loads(get_last_release_content())

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

  with open(filepath, 'r', encoding='utf-8') as file:
    other_language = json.load(file)

  print(f"\nLanguage: {language}")
  convert(old_english, new_english, other_language, language)

  with open(filepath, 'w', encoding='utf-8') as file:
    json.dump(other_language, file, ensure_ascii=False, indent=2)

print("\n")

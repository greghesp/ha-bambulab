import argparse
import base64
import glob
import json
import os
import subprocess
import sys

import requests

try:
    import cloudscraper
except ImportError:  # pragma: no cover - optional dependency
    cloudscraper = None

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - optional dependency
    curl_requests = None


DEFAULT_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://translate.google.com/",
}


def _browser_headers(headers=None):
    merged = dict(DEFAULT_BROWSER_HEADERS)
    if headers:
        merged.update(headers)
    return merged


def get_request_session(client_name):
    client_name = (client_name or "requests").lower()
    if client_name == "requests":
        return requests.Session()
    if client_name == "cloudscraper":
        if cloudscraper is None:
            raise RuntimeError("cloudscraper is not installed. Install it with: pip install cloudscraper")
        return cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "linux", "desktop": True})
    if client_name == "curl_cffi":
        if curl_requests is None:
            raise RuntimeError("curl_cffi is not installed. Install it with: pip install curl_cffi")
        return curl_requests.Session(impersonate="chrome")
    raise ValueError(f"Unsupported client: {client_name}")


def send_request(session, method, url, **kwargs):
    headers = _browser_headers(kwargs.pop("headers", None))
    response = session.request(method, url, headers=headers, timeout=30, **kwargs)
    return response


def parse_args():
    parser = argparse.ArgumentParser(description="Translate JSON locale files with browser-like HTTP request support.")
    parser.add_argument(
        "--client",
        choices=["requests", "cloudscraper", "curl_cffi"],
        default=os.getenv("AUTO_TRANSLATE_CLIENT", "cloudscraper").lower(),
        help="HTTP client used for Google Translate and GitHub requests.",
    )
    return parser.parse_args()


ARGS = parse_args()
HTTP_SESSION = get_request_session(ARGS.client)


def get_google_translation(to, content):
  sourceLang = 'en'
  targetLang = to
  contentStr = content.strip('"')
  url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sourceLang}&tl={targetLang}&dt=t&q={contentStr}"
  response = send_request(HTTP_SESSION, "GET", url)

    # -SessionVariable Session `
    # -UserAgent ([Microsoft.PowerShell.Commands.PSUserAgent]::Chrome) `
    # -Method Get `
    # -ContentType 'application/json'
  
  try:
    json = response.json()
  except:
    print(f"Google JSON response failed for: {url}")
    print(response.text)

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
    response = send_request(HTTP_SESSION, "GET", releases_url, headers=headers)
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
    response = send_request(HTTP_SESSION, "GET", content_url, headers=headers)
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

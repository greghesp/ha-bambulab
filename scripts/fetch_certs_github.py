"""
Script to fetch the printer certificates from Bambu Lab's GitHub repository and save it to the bambu.cert file.
"""

import asyncio
import os

import aiohttp

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


async def fetch_certificate():
    url = "https://raw.githubusercontent.com/bambulab/BambuStudio/refs/heads/master/resources/cert/printer.cer"

    try:
        print(f"Fetching certificates from: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")

                cert_content = await response.text()

        # Write the certificate bundle to bambu.cert
        cert_path = (
            f"{SCRIPT_DIR}/../custom_components/bambu_lab/pybambu/certs/bambu.cert"
        )
        with open(cert_path, "w") as f:
            f.write(cert_content)

        print(f"Successfully wrote certificates to {cert_path}")

    except Exception as error:
        print(f"Error fetching certificates: {error}")
        raise


asyncio.run(fetch_certificate())

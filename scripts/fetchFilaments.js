import { writeFileSync } from 'fs';


  const baseUrl =
    "https://api.github.com/repos/bambulab/BambuStudio/contents/resources/profiles/BBL/filament";
  const filamentIds= [];

  try {
    // First fetch the directory listing
    console.log("Fetching filament IDs from:", baseUrl);
    const response = await fetch(baseUrl);
    const files = await response.json();

    // Process each .json file
    for (const file of files) {
      if (file.name.endsWith(".json")) {
        const contentResponse = await fetch(file.download_url);
        const content = await contentResponse.json();

        if (content.filament_id) {
          filamentIds.push(content);
        }
      }
    }

    // Write the data to filament.json
    writeFileSync("filament.json", JSON.stringify(filamentIds, null, 2));
    console.log("Successfully wrote filament data to filament.json");

    
  } catch (error) {
    console.error("Error fetching filament IDs:", error);
  }
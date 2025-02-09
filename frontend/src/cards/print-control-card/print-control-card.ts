import { customElement, state, property } from "lit/decorators.js";
import { html, LitElement, nothing } from "lit";
import styles from "./card.styles";

import { registerCustomCard } from "../../utils/custom-cards";
import { PRINT_CONTROL_CARD_EDITOR_NAME, PRINT_CONTROL_CARD_NAME } from "./const";

registerCustomCard({
  type: PRINT_CONTROL_CARD_NAME,
  name: "Bambu Lab Print Control Card",
  description: "Card for controlling a Bambu Lab Printer",
});

interface Entity {
  entity_id: string;
  device_id: string;
  labels: any[];
  translation_key: string;
  platform: string;
  name: string;
}

interface Result {
  pick_image: Entity | null;
  skipped_objects: Entity | null;
  printable_objects: Entity | null;
  pause: Entity | null;
  resume: Entity | null;
  stop: Entity | null;
}

interface PrintableObject {
  name: string;
  skipped: boolean;
  to_skip: boolean;
}

@customElement(PRINT_CONTROL_CARD_NAME)
export class PrintControlCard extends LitElement {
  
  static styles = styles;

  // private property
  _hass;

  @state() private _states;
  @state() private _deviceId: any;
  @state() private _entities: any;

  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  _pick_image;
  _hiddenCanvas;
  _hiddenCtx;
  _visibleCanvas;
  _visibleCtx;
  _object_array;
 
  constructor() {
    super()
    this._hiddenCanvas = document.createElement('canvas');
    this._hiddenCanvas.width = 512;
    this._hiddenCanvas.height = 512;
    this._hiddenCtx = this._hiddenCanvas.getContext('2d', { willReadFrequently: true });
    this._hoveredObject = 0;
  }

  public static async getConfigElement() {
    await import("./print-control-card-editor");
    return document.createElement(PRINT_CONTROL_CARD_EDITOR_NAME);
  }

  static getStubConfig() {
    return { entity: "sun.sun" };
  }

  setConfig(config) {
    this._deviceId = config.printer;

    if (!config.printer) {
      throw new Error("You need to select a Printer");
    }

    if (this._hass) {
      this.hass = this._hass;
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._states = hass.states;
    this._filterBambuDevices();
  }

  private rgbaToInt(r, g, b, a) {
    return r | (g << 8) | (b << 16) | (a << 24);
  }
  
  private _updateCanvas() {
    // Now find the visible canvas.
    const canvas = this.shadowRoot!.getElementById('canvas') as HTMLCanvasElement;
    this._visibleCtx = canvas.getContext('2d', { willReadFrequently: true })!;

    // Add the click event listener to it that looks up the clicked pixel color and toggles any found object on or off.
    canvas.addEventListener('click', (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const imageData = this._hiddenCtx.getImageData(x, y, 1, 1).data;
      const [r, g, b, a] = imageData;

      const key = this.rgbaToInt(r, g, b, 0); // For integer comparisons we set the alpha to 0.
      if (key != 0)
      {
        if (!this._objects.get(key)!.skipped) {
          const value = this._objects.get(key)!
          value.to_skip = !value.to_skip
          this._updateObject(key, value);
        }
      }
    });

    // Now create a the image to load the pick image into from home assistant.
    this._pick_image = new Image();
    this._pick_image.onload = () => {
      this._hiddenCtx.drawImage(this._pick_image, 0, 0)
      this._colorizeCanvas();
    }

    // Finally set the home assistant image URL into it to load the image.
    this._pick_image.src = this._getPickImageUrl();
  }

  private _getPickImageUrl() {
    if (this._entities.pick_image) {
      const entity = this._entities.pick_image;
      const timestamp = this._states[entity.entity_id].state;
      const accessToken = this._states[entity.entity_id].attributes?.access_token
      const imageUrl = `/api/image_proxy/${entity.entity_id}?token=${accessToken}&time=${timestamp}`;
      return imageUrl;
    }
    return '';
  }

  private _getSkippedObjects() {
    if (this._entities?.skipped_objects) {
      const entity = this._entities.skipped_objects;
      const value = this._states[entity.entity_id].attributes['objects'];
      return value
    }
    return null;
  }

  private _getPrintableObjects() {
    if (this._entities?.printable_objects) {
      const entity = this._entities.printable_objects;
      const value = this._states[entity.entity_id].attributes['objects'];
      return value
    }
    return null;
  }

  private _isEntityUnavailable(entity: Entity): boolean {
    return this._states[entity?.entity_id]?.state == 'unavailable';
  }

  private _clickButton(entity: Entity) {
    const data = {
      entity_id: entity.entity_id
    }
    this._hass.callService('button', 'press', data);
  }

  private _colorizeCanvas() {
    if (this._visibleCtx == undefined) {
      // Lit reactivity can come through here before we're fully initialized.
      return
    }

    // Now we colorize the image based on the list of skipped objects.
    const WIDTH = 512;
    const HEIGHT = 512

    // Read original pick image into a data buffer so we can read the pixels.
    const readImageData = this._hiddenCtx.getImageData(0, 0, WIDTH, HEIGHT);
    const readData = readImageData.data;

    // Overwrite the display image with the starting pick image
    this._visibleCtx.putImageData(readImageData, 0, 0);  

    // Read the data into a buffer that we'll write to to modify the pixel colors.
    const writeImageData = this._visibleCtx.getImageData(0, 0, WIDTH, HEIGHT);
    const writeData = writeImageData.data;
    const writeDataView = new DataView(writeData.buffer);
  
    const red = this.rgbaToInt(255, 0, 0, 255);   // For writes we set it to 255 (fully opaque).
    const green = this.rgbaToInt(0, 255, 0, 255); // For writes we set it to 255 (fully opaque).
    const blue = this.rgbaToInt(0, 0, 255, 255);  // For writes we set it to 255 (fully opaque).

    let lastPixelWasHoveredObject = false
    for (let y = 0; y < HEIGHT; y++) {
      for (let x = 0; x < WIDTH; x++) {
        const i = (y * 4 * HEIGHT) + x * 4;
        const key = this.rgbaToInt(readData[i], readData[i + 1], readData[i + 2], 0); // For integer comparisons we set the alpha to 0.
        
        // If the pixel is not clear we need to change it.
        if (key != 0) {
          // Color the object based on it's to_skip state.
          if (this._objects.get(key)?.to_skip) {
            writeDataView.setUint32(i, red, true);
          }
          else {
            writeDataView.setUint32(i, green, true);
          }

          if (key == this._hoveredObject) {
            // Check to see if we need to render the left border if the pixel to the left is not the hovered object.
            if (x > 0) {
              const j = i - 4
              const left = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (left != key)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
            if (x > 1) {
              const j = i - 4 * 2
              const left = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (left != key)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }

            // Check to see if we need to render the top border if the pixel above is not the hovered object.
            if (y > 0) {
              const j = i - WIDTH * 4
              const top = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (top != key)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
            if (y > 1) {
              const j = i - WIDTH * 4 * 2
              const top = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (top != key)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }

            // Check to see if pixel to the right is not the hovered object to draw right border.
            if (x < (WIDTH - 1)) {
              const j = i + 4
              const right = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (right != this._hoveredObject)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
            // And the next one over for a 2px border.
            if (x < (WIDTH - 2)) {
              const j = i + 4 * 2
              const right = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (right != this._hoveredObject)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
            
            // Check to see if pixel above was the hovered object to draw bottom border.
            if (y < (HEIGHT - 1)) {
              const j = i + WIDTH * 4
              const below = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (below != this._hoveredObject)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
            // And the next one over for a 2px border.
            if (y < (HEIGHT - 2)) {
              const j = i + WIDTH * 4 * 2
              const below = this.rgbaToInt(readData[j], readData[j+1], readData[j+2], 0);
              if (below != this._hoveredObject)
              {
                writeDataView.setUint32(i, blue, true);
              }
            }
          }
        }
      }
    }

    // Put the modified image data back into the canvas
    this._visibleCtx.putImageData(writeImageData, 0, 0);  
  }

  @property({ type: Boolean }) _popupVisible = false
  @property({ type: Map }) _objects = new Map<number, PrintableObject>();
  @property({ type: Number }) _hoveredObject = 0;
  @property({ type: Map }) _skipped_objects = new Map<string, Object>();
  
  updated(changedProperties) {
    super.updated(changedProperties);
    if (changedProperties.has('_popupVisible') && this._popupVisible) {
      this._populateCheckboxList();
      this._updateCanvas();
    }
    
    if (changedProperties.has('_hoveredObject')) {
      this._colorizeCanvas();
    }
    else if (changedProperties.has('_objects')) {
      this._colorizeCanvas();
    }

    if (changedProperties.has('_skipped_objects')) {
      this._populateCheckboxList()
    }
  }

  render() {
    return html`
      <ha-card class="card">
        <div class="control-container">
          <button class="button" @click="${() => this._clickButton(this._entities?.pause)}" ?disabled="${this._isEntityUnavailable(this._entities?.pause)}">
            Pause
          </button>
          <button class="button" @click="${() => this._clickButton(this._entities?.resume)}" ?disabled="${this._isEntityUnavailable(this._entities?.resume)}">
            Resume
          </button>
          <button class="button" @click="${() => this._clickButton(this._entities?.stop)}" ?disabled="${this._isEntityUnavailable(this._entities?.stop)}">
            Stop
          </button>
          <button class="button" @click="${this._togglePopup}">
            Skip
          </button>
        </div>
        ${this._popupVisible
          ? html`
              <div class="popup-background" @click="${this._togglePopup}"></div>
              <div class="popup">
                <div class="popup-header">Skip Objects</div>
                <div class="alpha-text">Alpha</div>
                <div class="popup-content">
                  <canvas id="canvas" width="512" height="512"></canvas>
                  <ul id="checkboxList"></ul>
                  <div class="checkbox-list">
                    ${Array.from(this._objects.keys()).map((key) => {
                      const item = this._objects.get(key)!;
                      return html`
                        <label @mouseover="${() => this._onMouseOverCheckBox(key)}" @mouseout="${() => this._onMouseOutCheckBox(key)}">
                          <input type="checkbox" .checked="${item.to_skip}" @change="${(e: Event) => this._toggleCheckbox(e, key)}" />
                          ${item.skipped ? item.name + " (already skipped)" : item.name}
                        </label>
                        <br />
                      `;
                  })}
                  </div>
                  <p>Select the object(s) you want to skip printing.</p>
                  <div class="button-container">
                    <button class="button" @click="${this._togglePopup}">
                      Cancel
                    </button>
                    <button class="button" @click="${this._callSkipObjectsService}" ?disabled="${this._isSkipButtonDisabled}">
                      Skip
                    </button>
                  </div>
                </div>
              </div>
            `
        : ''}
      </ha-card>
    `;
  }

  // Function to toggle popup visibility
  private _togglePopup() {
    this._popupVisible = !this._popupVisible;
  }

  // Method to check if the skip button should be disabled
  get _isSkipButtonDisabled() {
    for (const item of this._objects.values()) {
      if (item.to_skip && !item.skipped) {
        return false;  // Found an object that should allow skipping
      }
    }
    return true;  // No items meet the criteria
  }
  
  private _callSkipObjectsService() {
    const list = Array.from(this._objects.keys()).filter((key) => this._objects.get(key)!.to_skip).map((key) => key).join(',');
    const data = { "device_id": [this._deviceId], "objects": list }
    this._hass.callService("bambu_lab", "skip_objects", data).then(() => {
      console.log(`Service called successfully`);
    }).catch((error) => {
      console.error(`Error calling service:`, error);
    });
  }

  private _updateObject(key: number, value: PrintableObject) {
    this._objects.set(key, value);
    this._objects = new Map(this._objects); // Trigger Lit reactivity
  }

  // Toggle the checked state of an item when a checkbox is clicked
  private _toggleCheckbox(e: Event, key: number) {
    const skippedBool = this._objects.get(key)?.skipped;
    if (skippedBool) {
      // Force the checkbox to remain checked if the object has already been skipped.
      (e.target as HTMLInputElement).checked = true
    }
    else {
      const value = this._objects.get(key)!
      value.to_skip = !value.to_skip
      this._updateObject(key, value);
      this._hoveredObject = 0;
    }
  }

  // Function to handle hover
  _onMouseOverCheckBox(key: number) {
    this._hoveredObject = key
  };

  // Function to handle mouse out
  _onMouseOutCheckBox(key: number) {
    if (this._hoveredObject == key) {
      this._hoveredObject = 0
    }
  };

  // Function to populate the list of checkboxes
  private _populateCheckboxList() {
    // Populate the viewmodel
    const list = this._getPrintableObjects();
    if (list == undefined) {
      return
    }
    const skipped = this._getSkippedObjects();

    let objects = new Map<number, PrintableObject>();
    Object.keys(list).forEach(key => {
      const value = list[key];
      const skippedBool = skipped.includes(Number(key));
      objects.set(Number(key), { name: value, skipped: skippedBool, to_skip: skippedBool });
    });
    this._objects = objects;
  }

  private async _getEntity(entity_id) {
    return await this._hass.callWS({
      type: "config/entity_registry/get",
      entity_id: entity_id,
    });
  }

  private async _filterBambuDevices() {
    const result: Result = {
      pick_image: null,
      skipped_objects: null,
      printable_objects: null,
      pause: null,
      resume: null,
      stop: null,
    };
    // Loop through all hass entities, and find those that belong to the selected device
    for (let key in this._hass.entities) {
      const value = this._hass.entities[key];
      if (value.device_id === this._deviceId) {
        const r = await this._getEntity(value.entity_id);
        if (r.unique_id.includes("pick_image")) {
          result.pick_image = value;
        }
        else if (r.unique_id.includes("skipped_objects")) {
          result.skipped_objects = value;
        }
        else if (r.unique_id.includes("printable_objects")) {
          result.printable_objects = value;
        }
        else if (r.unique_id.includes("pause")) {
          result.pause = value
        }
        else if (r.unique_id.includes("resume")) {
          result.resume = value
        }
        else if (r.unique_id.includes("stop")) {
          result.stop = value
        }
      }
    }

    this._entities = result;
    this._skipped_objects = this._states[result.skipped_objects!.entity_id].state
  }
}

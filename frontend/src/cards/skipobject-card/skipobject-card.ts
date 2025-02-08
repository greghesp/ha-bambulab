import { customElement, state, property } from "lit/decorators.js";
import { html, LitElement, nothing } from "lit";
import styles from "./card.styles";

import { registerCustomCard } from "../../utils/custom-cards";
import { SKIPOBJECT_CARD_EDITOR_NAME, SKIPOBJECT_CARD_NAME } from "./const";

registerCustomCard({
  type: SKIPOBJECT_CARD_NAME,
  name: "Bambu Lab Skip Object Card",
  description: "Card for Skip Object",
});

interface Sensor {
  entity_id: string;
  device_id: string;
  labels: any[];
  translation_key: string;
  platform: string;
  name: string;
}

interface Result {
  pick_image: Sensor | null;
  skipped_objects: Sensor | null;
  printable_objects: Sensor | null;
}

interface PrintableObject {
  name: string;
  skipped: boolean;
  to_skip: boolean;
}

@customElement(SKIPOBJECT_CARD_NAME)
export class SKIPOBJECT_CARD extends LitElement {
  
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
    this._object_array = new Array();
    this._hoveredObject = 0;
  }

  public static async getConfigElement() {
    await import("./skipobject-card-editor");
    return document.createElement(SKIPOBJECT_CARD_EDITOR_NAME);
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
    this.filterBambuDevices();
  }

  rgbaToInt(r, g, b, a) {
    return r | (g << 8) | (b << 16) | (a << 24);
  }
  
  _updateCanvas() {
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
        if (!this.objects.get(key)!.skipped) {
          const value = this.objects.get(key)!
          value.to_skip = !value.to_skip
          this.objects.set(key, value);
          this._colorizeCanvas();
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
    this._pick_image.src = this._get_pick_image_url();
  }

  _get_pick_image_url() {
    if (this._entities.pick_image) {
      const entity = this._entities.pick_image;
      const timestamp = this._states[entity.entity_id].state;
      const accessToken = this._states[entity.entity_id].attributes?.access_token
      const imageUrl = `/api/image_proxy/${entity.entity_id}?token=${accessToken}&time=${timestamp}`;
      return imageUrl;
    }
    return '';
  }

  _get_skipped_objects() {
    if (this._entities.skipped_objects) {
      const entity = this._entities.skipped_objects;
      const value = this._states[entity.entity_id].attributes['objects'];
      return value
    }
    return null;
  }

  _get_printable_objects() {
    if (this._entities.printable_objects) {
      const entity = this._entities.printable_objects;
      const value = this._states[entity.entity_id].attributes['objects'];
      return value
    }
    return null;
  }

  _colorizeCanvas() {
    // Now we colorize the image based on the list of skipped objects.
    this._visibleCtx.drawImage(this._pick_image, 0, 0)

    // Create an ImageData object
    const imageData = this._visibleCtx.getImageData(0, 0, 512, 512);
    const data = imageData.data;
  
    // Replace the target RGB value with red
    const red = this.rgbaToInt(255, 0, 0, 255);   // For writes we set it to 255 (fully opaque).
    const green = this.rgbaToInt(0, 255, 0, 255); // For writes we set it to 255 (fully opaque).
    const blue = this.rgbaToInt(0, 0, 255, 255);  // For writes we set it to 255 (fully opaque).

    for (let i = 0; i < data.length; i += 4) {
      const key = this.rgbaToInt(data[i], data[i + 1], data[i + 2], 0); // For integer comparisons we set the alpha to 0.
      
      if ((key != 0) && (this._hoveredObject == key)) {
        const dataView = new DataView(data.buffer);
        dataView.setUint32(i, blue, true);
      }
      else if (this.objects.get(key)?.to_skip) {
        const dataView = new DataView(data.buffer);
        dataView.setUint32(i, red, true);
      }
      else if (key != 0) {
        const dataView = new DataView(data.buffer);
        dataView.setUint32(i, green, true);
      }
    }

    // Put the modified image data back into the canvas
    this._visibleCtx.putImageData(imageData, 0, 0);  
  }

  @property({ type: Boolean }) _popupVisible = false
  @property({ type: Map }) objects = new Map<number, PrintableObject>();
  @property({ type: Number }) _hoveredObject = 0;

  render() {
    return html`
      <ha-card class="card">
        <button class="button" @click="${this._togglePopup}">
          Skip Objects
        </button>
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
                    ${Array.from(this.objects.keys()).map((key) => {
                      const item = this.objects.get(key)!;
                      return html`
                        <label
                          @mouseover="${() => this.handleMouseOver(key)}"
                          @mouseout="${() => this.handleMouseOut(key)}"
                        >
                          <input
                              type="checkbox"
                              .checked="${item.to_skip}"
                              @change="${(e: Event) => this.toggleCheckbox(e, key)}"
                          />
                          ${item.skipped ? item.name + " (already skipped)" : item.name}
                        </label><br />
                      `;
                  })}
                  </div>
                  <p>Select the object(s) you want to skip printing.</p>
                  <button id="cancel" @click="${this._togglePopup}">Cancel</button>
                  <button id="skip" @click="${this._skipObjects}">Skip</button>
                </div>
              </div>
            `
        : ''}
      </ha-card>
    `;
  }

  _skipObjects() {
    const list = Array.from(this.objects.keys()).filter((key) => this.objects.get(key)!.to_skip).map((key) => key).join(',');
    const data = { "device_id": [this._deviceId], "objects": list }
    this._hass.callService("bambu_lab", "skip_objects", data).then(() => {
      console.log(`Service called successfully`);
    }).catch((error) => {
      console.error(`Error calling service:`, error);
    });
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    if (changedProperties.has('_popupVisible') && this._popupVisible) {
      this._populateCheckboxList();
      this._updateCanvas();
    }
    if (changedProperties.has('_hoveredObject')) {
      this._colorizeCanvas();
    }
  }

  // Function to toggle popup visibility
  private _togglePopup() {
    this._popupVisible = !this._popupVisible;
  }

  // Toggle the checked state of an item when a checkbox is clicked
  toggleCheckbox(e: Event, key: number) {
    const skippedBool = this.objects.get(key)?.skipped;
    if (skippedBool) {
      // Force the checkbox to remain checked if the object has already been skipped.
      (e.target as HTMLInputElement).checked = true
    }
    else {
      const value = this.objects.get(key)!
      value.to_skip = !value.to_skip
      this.objects.set(key, value);
      this._hoveredObject = 0;
    }
  }

  // Function to handle hover
  handleMouseOver(key: number) {
    this._hoveredObject = key
  };

  // Function to handle mouse out
  handleMouseOut(key: number) {
    if (this._hoveredObject == key) {
      this._hoveredObject = 0
    }
  };

  // Function to populate the list of checkboxes
  private _populateCheckboxList() {
    // Populate the viewmodel
    const list = this._get_printable_objects();
    const skipped = this._get_skipped_objects();

    let objects = new Map<number, PrintableObject>();
    Object.keys(list).forEach(key => {
      const value = list[key];
      const skippedBool = skipped.includes(Number(key));
      objects.set(Number(key), { name: value, skipped: skippedBool, to_skip: skippedBool });
    });
    this.objects = objects;
    this.requestUpdate()
  }

  private async getEntity(entity_id) {
    return await this._hass.callWS({
      type: "config/entity_registry/get",
      entity_id: entity_id,
    });
  }

  private async filterBambuDevices() {
    const result: Result = {
      pick_image: null,
      skipped_objects: null,
      printable_objects: null,
    };
    // Loop through all hass entities, and find those that belong to the selected device
    for (let key in this._hass.entities) {
      const value = this._hass.entities[key];
      if (value.device_id === this._deviceId) {
        const r = await this.getEntity(value.entity_id);
        if (r.unique_id.includes("pick_image")) {
          result.pick_image = value;
        }
        else if (r.unique_id.includes("skipped_objects")) {
          result.skipped_objects = value;
        }
        else if (r.unique_id.includes("printable_objects")) {
          result.printable_objects = value;
        }
      }
    }

    this._entities = result;
  }
}

import { customElement, state, property } from "lit/decorators.js";
import { css, html, LitElement, nothing } from "lit";

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
}

@customElement(SKIPOBJECT_CARD_NAME)
export class SKIPOBJECT_CARD extends LitElement {
  
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
    this._hiddenCtx = this._hiddenCanvas.getContext('2d');
    this._object_array = new Array();
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
    this._visibleCtx = canvas.getContext('2d')!;

    // Add the click event listener to it that looks up the clicked pixel color and toggles any found object on or off.
    canvas.addEventListener('click', (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const imageData = this._hiddenCtx.getImageData(x, y, 1, 1).data;
      const [r, g, b, a] = imageData;

      const pixelColor = this.rgbaToInt(r, g, b, 255)
      const index = this._object_array.indexOf(pixelColor)
      if (index != -1)
      {
        this._object_array.splice(index, 1);
      }
      else
      {
        this._object_array.push(pixelColor);
      }
      this._colorizeCanvas();
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

  _colorizeCanvas() {
      // Now we colorize the image based on the list of skipped objects.
      this._visibleCtx.drawImage(this._pick_image, 0, 0)

      // Create an ImageData object
      const imageData = this._visibleCtx.getImageData(0, 0, 512, 512);
      const data = imageData.data;
    
      // Replace the target RGB value with red
      const clear = this.rgbaToInt(0, 0, 0, 255);
      const red = this.rgbaToInt(255, 0, 0, 255);
      const green = this.rgbaToInt(0, 255, 0, 255);

      for (let i = 0; i < data.length; i += 4) {
        const pixelColor = this.rgbaToInt(data[i], data[i + 1], data[i + 2], 255);
        
        if (this._object_array.includes(pixelColor)) {
          const dataView = new DataView(data.buffer);
          dataView.setUint32(i, red, true);
        }
        else if (pixelColor != clear) {
          const dataView = new DataView(data.buffer);
          dataView.setUint32(i, green, true);
        }
      }

      // Put the modified image data back into the canvas
      this._visibleCtx.putImageData(imageData, 0, 0);  
  }

  // Style for the card and popup
  static styles = css`
    .card {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 16px;
      background: var(--card-background-color);
    }
    .button {
      padding: 10px 20px;
      font-size: 16px;
      background-color: var(--primary-color);
      color: white;
      border: none;
      cursor: pointer;
    }
    .popup {
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      background: white;
      padding: 20px;
      border: 1px solid #ccc;
      box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
      z-index: 1000;
    }
    .popup-background {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      z-index: 999;
    }
    .popup-header {
      font-size: 18px;
      margin-bottom: 10px;
      color: black; /* Ensure the header text is black */
    }
    .popup-content {
      font-size: 14px;
      color: black; /* Ensure the content text is black */
    }
  `;

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
                <div class="popup-content">
                  <canvas id="canvas" width="512" height="512"/>
                  <p>Click the object(s) you want to skip printing and then the confirm button once done.</p>
                  <button @click="${this._togglePopup}">Confirm</button>
                </div>
              </div>
            `
          : ''}
      </ha-card>
    `;
  }

  updated(changedProperties) {
    if (changedProperties.has('_popupVisible') && this._popupVisible) {
      this._updateCanvas();
    }
  }

  // State to track popup visibility
  @property({ type: Boolean }) _popupVisible = false

  // Function to toggle popup visibility
  private _togglePopup() {
    this._popupVisible = !this._popupVisible;
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
    };
    // Loop through all hass entities, and find those that belong to the selected device
    for (let key in this._hass.entities) {
      const value = this._hass.entities[key];
      if (value.device_id === this._deviceId) {
        const r = await this.getEntity(value.entity_id);
        if (r.unique_id.includes("pick_image")) {
          result.pick_image = value;
        }
      }
    }

    this._entities = result;
  }
}

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

  _updateCanvas() {
    const canvas = this.shadowRoot!.getElementById('canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d')!;

    const image = new Image();
    image.src = this._get_pick_image_url();
    image.onload = function() {
      const width = canvas.width;
      const height = canvas.height;
      ctx.drawImage(image, 0, 0)
    
      // Create an ImageData object
      const imageData = ctx.getImageData(0, 0, width, height);
      const data = imageData.data;
    
      // Replace the target RGB value with red
      const targetRgb = { r: 5, g: 3, b: 0 }; // Example RGB value to replace

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        if (r === targetRgb.r && g === targetRgb.g && b === targetRgb.b) {
          data[i]     = 255; // Red
          data[i + 1] = 0;   // Green
          data[i + 2] = 0;   // Blue
          data[i + 3] = 255; // Alpha (opacity)
        }
        else if (r != 0 || g != 0 || b != 0)
        {
          data[i]     = 0;   // Red
          data[i + 1] = 255; // Green
          data[i + 2] = 0;   // Blue
          data[i + 3] = 255; // Alpha (opacity)
        }
      }
    
      // Put the image data on the canvas
      ctx.putImageData(imageData, 0, 0);
    }
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

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
  _new_object_array;
  _hoveredObject;
 
  constructor() {
    super()
    this._hiddenCanvas = document.createElement('canvas');
    this._hiddenCanvas.width = 512;
    this._hiddenCanvas.height = 512;
    this._hiddenCtx = this._hiddenCanvas.getContext('2d', { willReadFrequently: true });
    this._object_array = new Array();
    this._new_object_array = new Array();
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

      const pixelColor = this.rgbaToInt(r, g, b, 0); // For integer comparisons we set the alpha to 0.
      if (pixelColor != 0)
      {
        const index = this._object_array.indexOf(pixelColor);
        const new_index = this._new_object_array.indexOf(pixelColor);
        // Cannot toggle objects in the completed skipped objects list
        if (index == -1)
        {
          if (new_index != -1)
          {
            // Remove the element at 'new_index' from the array
            this._new_object_array.splice(new_index, 1);
          }
          else
          {
            // Add the element to the array
            this._new_object_array.push(pixelColor);
          }
        }
        this._colorizeCanvas();
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
    const clear = this.rgbaToInt(0, 0, 0, 0);     // For integer comparisons we set the alpha to 0.
    const red = this.rgbaToInt(255, 0, 0, 255);   // For writes we set it to 255 (fully opaque).
    const green = this.rgbaToInt(0, 255, 0, 255); // For writes we set it to 255 (fully opaque).
    const blue = this.rgbaToInt(0, 0, 255, 255);  // For writes we set it to 255 (fully opaque).

    for (let i = 0; i < data.length; i += 4) {
      const pixelColor = this.rgbaToInt(data[i], data[i + 1], data[i + 2], 0); // For integer comparisons we set the alpha to 0.
      
      if ((pixelColor != 0) && (this._hoveredObject == pixelColor)) {
        const dataView = new DataView(data.buffer);
        dataView.setUint32(i, blue, true);
      }
      else if (this._new_object_array.includes(pixelColor)) {
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
                  <canvas id="canvas" width="512" height="512"></canvas>
                  <ul id="checkboxList"></ul>
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
    const data = { "device_id": [this._deviceId], "objects": this._new_object_array.join(',') }
    this._hass.callService("bambu_lab", "skip_objects", data).then(() => {
      console.log(`Service called successfully`);
    }).catch((error) => {
      console.error(`Error calling service:`, error);
    });
  }

  updated(changedProperties) {
    if (changedProperties.has('_popupVisible') && this._popupVisible) {
      this._populateCheckboxList();
      this._updateCanvas();
    }
  }

  // State to track popup visibility
  @property({ type: Boolean }) _popupVisible = false

  // Function to toggle popup visibility
  private _togglePopup() {
    this._popupVisible = !this._popupVisible;
    if (this._popupVisible) {
      this._object_array = this._get_skipped_objects();
      this._new_object_array = this._object_array.slice();
    }
  }

  // Function to handle hover
  handleHover = (event) => {
    let id = event.target.htmlFor
    if (id == null) {
      id = event.target.id
    }
    this._hoveredObject = id;
    this._colorizeCanvas();
  };

  // Function to handle mouse out
  handleMouseOut = (event) => {
    let id = event.target.htmlFor
    if (id == null) {
      id = Number(event.target.id)
    }
    if (this._hoveredObject = id) {
      this._hoveredObject = 0;
    }
    this._colorizeCanvas();
  };

  // Function to handle mouse out
  handleChange = (event) => {
    const id = Number(event.target.id)
    const checked = event.target.checked
    if (this._object_array.includes(id))
    {
      // Already skipped objects must remain skipped
      event.target.checked = true
    }
    else if (checked)
    {
      this._new_object_array.push(id)
      // Clear hover visual so the change can be observed.
      this._hoveredObject = 0
    }
    else
    {
      const index = this._new_object_array.indexOf(id);
      this._new_object_array.splice(index, 1);
      // Clear hover visual so the change can be observed.
      this._hoveredObject = 0
    }
    this._colorizeCanvas();
  }

  // Function to populate the list of checkboxes
  private _populateCheckboxList() {
    const checkboxList = this.shadowRoot!.getElementById('checkboxList')!

    // Clear existing list items if any
    checkboxList.innerHTML = '';

    // Create and append list items dynamically
    const list = this._get_printable_objects();
    Object.keys(list).forEach(key => {
      const value = list[key];
      const listItem = document.createElement('li');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = key;
      checkbox.checked = this._new_object_array.includes(Number(key))
      const label = document.createElement('label');
      label.htmlFor = key;
      if (this._object_array.includes(Number(key))) {
        label.textContent = `${value} (already skipped)`;
      }
      else {
        label.textContent = value;
      }
      listItem.appendChild(checkbox);
      listItem.appendChild(label);
      // Add event listener to the checkbox and label for hover
      checkbox.addEventListener('mouseover', this.handleHover);
      label.addEventListener('mouseover', this.handleHover);
      // Add event listener to the checkbox and label for mouse out
      checkbox.addEventListener('mouseout', this.handleMouseOut);
      label.addEventListener('mouseout', this.handleMouseOut);
      // Add event listener to the checkbox for check state change
      checkbox.addEventListener('change', this.handleChange);
      checkboxList.appendChild(listItem);
    });
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

import { customElement } from "lit/decorators.js";
import { registerCustomCard } from "../../utils/custom-cards";
import { EXAMPLE_CARD_EDITOR_NAME, EXAMPLE_CARD_NAME } from "./const";
import { LitElement, html, css } from "lit";
import { property } from 'lit/decorators.js';

registerCustomCard({
  type: EXAMPLE_CARD_NAME,
  name: "Bambu Lab Example Card",
  description: "Card for Example",
});

@customElement(EXAMPLE_CARD_NAME)
export class EXAMPLE_CARD extends LitElement {
  
  // private property
  _hass;

  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  public static async getConfigElement() {
    await import("./example-card-editor");
    return document.createElement(EXAMPLE_CARD_EDITOR_NAME);
  }

  static getStubConfig() {
    return { entity: "sun.sun" };
  }

  setConfig() {
    if (this._hass) {
      this.hass = this._hass;
    }
  }

  set hass(hass) {
    this._hass = hass;
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
          Show Popup
        </button>
        ${this._popupVisible
          ? html`
              <div class="popup-background" @click="${this._togglePopup}"></div>
              <div class="popup">
                <div class="popup-header">Popup Title</div>
                <div class="popup-content">
                  <p>This is a popup with some HTML content. You can include anything!</p>
                  <p><strong>Example:</strong> <em>HTML elements, links, images, etc.</em></p>
                  <button @click="${this._togglePopup}">Close</button>
                </div>
              </div>
            `
          : ''}
      </ha-card>
    `;
  }

  // State to track popup visibility
  @property({ type: Boolean }) private _popupVisible = false

  // Function to toggle popup visibility
  private _togglePopup() {
    this._popupVisible = !this._popupVisible;
  }
}

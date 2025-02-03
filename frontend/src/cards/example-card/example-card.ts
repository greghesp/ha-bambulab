import { customElement } from "lit/decorators.js";
import { registerCustomCard } from "../../utils/custom-cards";
import { EXAMPLE_CARD_EDITOR_NAME, EXAMPLE_CARD_NAME } from "./const";
import { html, LitElement, nothing } from "lit";

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

  render() {
    return html`
      <ha-card>
        <div class="card-content">Example Content</div>
      </ha-card>
    `;
  }
}

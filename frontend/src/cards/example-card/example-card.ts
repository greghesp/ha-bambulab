import { customElement, state } from "lit/decorators.js";
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
  @state() private _config?;
  @state() private _hass: any;

  public static async getConfigElement() {
    await import("./example-card-editor");
    return document.createElement(EXAMPLE_CARD_EDITOR_NAME);
  }

  static getStubConfig() {
    return { header: "Header Text", subtitle: "Subtitle Text", show_header: true };
  }

  setConfig(config) {
    if (this._hass) {
      this.hass = this._hass;
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
  }

  render() {
    return html`
      <ha-card>
        <div class="card-content">
          ${this._config?.show_header ? html`<h1>${this._config.header}</h1>` : nothing}
          <p>Subtitle: ${this._config?.subtitle}</p>
        </div>
      </ha-card>
    `;
  }
}

import { EXAMPLE_CARD_EDITOR_NAME } from "./const";
import { customElement, state } from "lit/decorators.js";
import { LitElement, html } from "lit";

@customElement(EXAMPLE_CARD_EDITOR_NAME)
export class ExampleCardEditor extends LitElement {
  @state() private _config?;

  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  public setConfig(config): void {
    this._config = config;
  }

  configChanged(newConfig) {
    const event = new Event("config-changed", {
      bubbles: true,
      composed: true,
    });
    event["detail"] = { config: newConfig };
    this.dispatchEvent(event);
  }

  render() {
    return html` <div>Example Editor</div> `;
  }
}

import { PRINT_CONTROL_CARD_EDITOR_NAME, PRINTER_MODELS } from "./const";
import { INTEGRATION_DOMAIN, MANUFACTURER } from "../../const";
import { customElement, state } from "lit/decorators.js";
import { LitElement, html } from "lit";

const filterCombinations = PRINTER_MODELS.map((model) => ({
  manufacturer: MANUFACTURER,
  model: model,
}));

const NEW_SCHEMA = [
  {
    name: "printer",
    label: "Printer",
    selector: { device: { filter: filterCombinations } },
  },
];

@customElement(PRINT_CONTROL_CARD_EDITOR_NAME)
export class PrintControlCardEditor extends LitElement {
  @state() private _config?;
  @state() private hass: any;

  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  public setConfig(config): void {
    this._config = config;
  }

  _handleValueChanged(ev) {
    const messageEvent = new CustomEvent("config-changed", {
      detail: { config: ev.detail.value },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(messageEvent);
  }

  render() {
    return html`
      <div>
        <ha-form
          .hass=${this.hass}
          .data=${this._config}
          .schema=${NEW_SCHEMA}
          .computeLabel=${(schema) => schema.label}
          @value-changed=${this._handleValueChanged}
        ></ha-form>
      </div>
    `;
  }
}

import { AMS_CARD_EDITOR_NAME, AMS_MODELS } from "./const";
import { INTEGRATION_DOMAIN, MANUFACTURER } from "../../const";
import { customElement, state } from "lit/decorators.js";
import { LitElement, html, nothing } from "lit";
import memoizeOne from "memoize-one";

// https://www.home-assistant.io/docs/blueprint/selectors/#select-selector
const filterCombinations = AMS_MODELS.map((model) => ({
  manufacturer: MANUFACTURER,
  model: model,
}));

@customElement(AMS_CARD_EDITOR_NAME)
export class AmsCardEditor extends LitElement {
  @state() private _config?;
  @state() private hass: any;

  public setConfig(config): void {
    this._config = config;
  }

  private _schema = memoizeOne((showHeader: boolean) => [
    {
      name: "header",
      label: "Card Header",
      selector: { text: {} },
      required: false,
    },
    { name: "show_header", label: "Show Header", selector: { boolean: false } },
    ...(showHeader
      ? [
          {
            name: "subtitle",
            label: "Subtitle",
            selector: { text: {} },
          },
        ]
      : ""),
    {
      name: "ams",
      label: "AMS",
      selector: { device: { filter: filterCombinations } },
    },
    {
      name: "style",
      label: "Card Style",
      selector: {
        select: {
          options: [
            { label: "Vector", value: "vector" },
            { label: "Graphic", value: "graphic" },
          ],
        },
      },
    },
  ]);

  _handleValueChanged(ev) {
    const messageEvent = new CustomEvent("config-changed", {
      detail: { config: ev.detail.value },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(messageEvent);
  }

  render() {
    const schema = this._schema(this._config!.header !== undefined);
    const data = {
      show_header: this._config!.header !== undefined,
      ...this._config,
    };
    return html`
      <div>
        <ha-form
          .hass=${this.hass}
          .data=${this._config}
          .schema=${schema}
          .computeLabel=${(s) => s.label}
          @value-changed=${this._handleValueChanged}
        ></ha-form>
      </div>
    `;
  }
}

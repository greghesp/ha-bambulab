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

  private _schema = memoizeOne((showInfoBar: boolean) => [
    { name: "show_info_bar", label: "Show Info Bar", selector: { boolean: true } },
    ...(showInfoBar
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

  render() {
    const schema = this._schema(this._config.show_info_bar);

    return html`
      <div>
        <ha-form
          .hass=${this.hass}
          .data=${this._config}
          .schema=${schema}
          .computeLabel=${(s) => s.label}
          @value-changed=${this._valueChange}
        ></ha-form>
      </div>
    `;
  }

  private _valueChange(ev: CustomEvent): void {
    let config = ev.detail.value;

    const event = new Event("config-changed", {
      bubbles: true,
      composed: true,
    });
    event["detail"] = { config };
    this.dispatchEvent(event);
  }
}

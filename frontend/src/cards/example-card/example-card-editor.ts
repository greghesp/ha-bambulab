import { EXAMPLE_CARD_EDITOR_NAME } from "./const";
import { customElement, state } from "lit/decorators.js";
import { LitElement, html } from "lit";
import memoizeOne from "memoize-one";

@customElement(EXAMPLE_CARD_EDITOR_NAME)
export class ExampleCardEditor extends LitElement {
  @state() private _config?;
  @state() private hass: any;

  public setConfig(config): void {
    this._config = config;
  }

  private _schema = memoizeOne((hideHeader: boolean) => [
    {
      name: "show_header",
      label: "Show Header",
      type: "grid",
      selector: { boolean: {} },
    },
    ...(hideHeader
      ? ([
          {
            name: "header",
            label: "Header",
            selector: { text: {} },
          },
        ] as const)
      : []),
    {
      name: "subtitle",
      label: "Subtitle",
      selector: { text: {} },
    },
  ]);

  render() {
    const schema = this._schema(this._config.show_header);

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

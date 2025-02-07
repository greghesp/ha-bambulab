import { customElement, state } from "lit/decorators.js";
import { html, LitElement, nothing } from "lit";

import { registerCustomCard } from "../../utils/custom-cards";
import { AMS_CARD_EDITOR_NAME, AMS_CARD_NAME } from "./const";
import styles from "./card.styles";
import "./components/spool/spool.ts";
import "./vector-ams-card/vector-ams-card";
import "./graphic-ams-card/graphic-ams-card";

registerCustomCard({
  type: AMS_CARD_NAME,
  name: "Bambu Lab AMS Card",
  description: "Card for AMS entity",
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
  humidity: Sensor | null;
  temperature: Sensor | null;
  spools: Sensor[];
}

@customElement(AMS_CARD_NAME)
export class AMS_CARD extends LitElement {
  // private property
  @state() private _hass?;
  @state() private _subtitle;
  @state() private _entity;
  @state() private _deviceId: any;
  @state() private _entities: any;
  @state() private _states;
  @state() private _style;
  @state() private _showInfoBar!: boolean | true;

  static styles = styles;

  public getLayoutOptions() {
    return {
      grid_rows:
        this._style === "graphic" ? (this._showInfoBar ? 5 : 4) : this._showInfoBar ? 4 : 3,
      grid_columns: 4,
      grid_min_rows:
        this._style === "graphic" ? (this._showInfoBar ? 5 : 4) : this._showInfoBar ? 4 : 3,
      grid_min_columns: 4,
    };
  }

  setConfig(config) {
    this._subtitle = config.subtitle === "" ? nothing : config.subtitle;
    this._entities = config._entities;
    this._deviceId = config.ams;
    this._style = config.style;
    this._showInfoBar = config.show_info_bar;

    if (!config.ams) {
      throw new Error("You need to select an AMS");
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

  render() {
    if (this._style == "graphic") {
      return html`
        <graphic-ams-card
          .subtitle="${this._subtitle}"
          .entities="${this._entities}"
          .states="${this._states}"
          .showInfoBar=${this._showInfoBar}
        />
      `;
    } else {
      return html`
        <vector-ams-card
          .subtitle="${this._subtitle}"
          .entities="${this._entities}"
          .states="${this._states}"
          .showInfoBar=${this._showInfoBar}
        />
      `;
    }
  }

  public static async getConfigElement() {
    await import("./ams-card-editor");
    return document.createElement(AMS_CARD_EDITOR_NAME);
  }

  static getStubConfig() {
    return {
      entity: "",
      header: "",
      subtitle: "",
      style: "vector",
    };
  }

  private async getEntity(entity_id) {
    return await this._hass.callWS({
      type: "config/entity_registry/get",
      entity_id: entity_id,
    });
  }

  private async filterBambuDevices() {
    const result: Result = {
      humidity: null,
      temperature: null,
      spools: [],
    };
    // Loop through all hass entities, and find those that belong to the selected device
    for (let key in this._hass.entities) {
      const value = this._hass.entities[key];
      if (value.device_id === this._deviceId) {
        const r = await this.getEntity(value.entity_id);
        if (r.unique_id.includes("humidity")) {
          result.humidity = value;
        } else if (r.unique_id.includes("temp")) {
          result.temperature = value;
        } else if (r.unique_id.includes("tray")) {
          result.spools.push(value);
        }
      }
    }

    this._entities = result;
  }
}

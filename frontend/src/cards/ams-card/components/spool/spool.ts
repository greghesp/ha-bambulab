import { customElement, property } from "lit/decorators.js";
import { html, LitElement, nothing } from "lit";
import styles from "./spool.styles";
import { getContrastingTextColor } from "../../../../utils/helpers";

@customElement("bl-spool")
export class Spool extends LitElement {
  @property({ type: Boolean }) public active: boolean = false;
  @property({ type: String }) public color;
  @property({ type: String }) public tag_uid;
  @property({ type: Number }) public remaining;
  @property({ type: Number }) private maxSpoolHeight: number = 0;
  @property({ type: Number }) private minSpoolHeight: number = 0;
  @property({ type: Number }) private remainHeight: number = 0;
  @property({ type: Number }) private resizeObserver: ResizeObserver | null = null;

  static styles = styles;

  connectedCallback() {
    super.connectedCallback();
    // Start observing the parent element for size changes

    this.resizeObserver = new ResizeObserver(() => {
      this.calculateHeights();
      this.updateLayers();
    });
    const rootNode = this.getRootNode() as ShadowRoot;
    const parent = this.parentElement || (rootNode instanceof ShadowRoot ? rootNode.host : null);
    if (parent) {
      this.resizeObserver.observe(parent);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    // Stop observing when the component is removed
    if (this.resizeObserver) {
      this.resizeObserver?.disconnect();
    }
  }

  firstUpdated() {
    this.updateLayers();
  }

  render() {
    return html`
      <div class="v-spool-container">
        <div class="v-spool"></div>
        <div
          class="string-roll-container"
          style="animation: ${this.active ? "wiggle 3s linear infinite" : ""}"
        >
          <div
            class="v-string-roll"
            id="v-string-roll"
            style="background: ${this.color}; height: ${this.remainHeight.toFixed(2)}%"
          >
            ${this.active ? html`<div class="v-reflection"></div>` : nothing}
            ${this.getRemainingValue().type == "unknown" ||
            this.getRemainingValue().type == "generic"
              ? ""
              : html` <div class="remaining-percent"><p>${this.remaining}%</p></div> `}
          </div>
        </div>
        <div class="v-spool"></div>
      </div>
    `;
  }

  updateLayers() {
    // Query the #string-roll element inside this component’s shadow DOM
    const stringRoll = (this.renderRoot as ShadowRoot).getElementById("v-string-roll");
    if (!stringRoll) return;

    const stringWidth = 2; // matches .string-layer width in CSS
    const rollWidth = stringRoll.offsetWidth; // container width

    // Calculate how many lines fit
    const numLayers = Math.floor(rollWidth / (stringWidth * 2)); // 2 = line width + gap

    // Clear previous layers
    const previousLayers = this.renderRoot.querySelectorAll(".v-string-layer");
    previousLayers.forEach((layer) => layer.remove());

    // Add new layers
    for (let i = 0; i < numLayers; i++) {
      const layer = document.createElement("div");
      layer.classList.add("v-string-layer");

      // Calculate left position = (index + 1) * (width*2) - width
      const leftPosition = (i + 1) * (stringWidth * 2) - stringWidth;
      layer.style.left = `${leftPosition}px`;

      stringRoll.appendChild(layer);
    }
  }

  getRemainingValue() {
    if (this.isAllZeros(this.tag_uid)) {
      return { type: "generic", value: 100 };
    } else if (this.remaining < 0) {
      return { type: "unknown", value: 100 };
    }
    return { type: "bambu", value: this.remaining };
  }

  isAllZeros(str) {
    return /^0+$/.test(str);
  }

  calculateHeights() {
    // If not a Bambu Sppol or remaining is less than 0
    // Less than 0 can represent no filament estimation enabled or bugged MQTT needing a printer restart
    if (
      this.getRemainingValue().type === "generic" ||
      this.getRemainingValue().type === "unknown"
    ) {
      this.remainHeight = 95;
    } else {
      // Get the container's height
      const container = this.renderRoot.querySelector(
        ".string-roll-container"
      ) as HTMLElement | null;
      const containerHeight = container?.offsetHeight || 0;

      // Calculate max spool height (95% of container height)
      this.maxSpoolHeight = containerHeight * 0.95;

      // Calculate min spool height (12% of max spool height)
      this.minSpoolHeight = this.maxSpoolHeight * 0.12;

      // Calculate remain height based on the remain percentage
      const remainPercentage = Math.min(Math.max(this.remaining, 0), 100); // Clamp remain to [0, 100]
      this.remainHeight =
        this.minSpoolHeight +
        (this.maxSpoolHeight - this.minSpoolHeight) * (remainPercentage / 100);

      // Ensure remainHeight is within bounds
      this.remainHeight = Math.min(this.remainHeight, this.maxSpoolHeight);
      this.requestUpdate();
    }
  }
}

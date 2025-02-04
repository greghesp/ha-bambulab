import { repository } from "../../package.json";

interface RegisterCardParams {
  type: string;
  name: string;
  description: string;
}
export function registerCustomCard(params: RegisterCardParams) {
  const windowWithCards = window as unknown as Window & {
    customCards: unknown[];
  };
  windowWithCards.customCards = windowWithCards.customCards || [];

  const cardPage = params.type.replace("-card", "").replace("ha-bambulab-", "");
  windowWithCards.customCards.push({
    ...params,
    preview: true,
    documentationURL: `${repository.url}/blob/main/docs/cards/${cardPage}.md`,
  });
}

export async function createCard(config, selector, instance) {
  const cardHelpers = await (window as any).loadCardHelpers();

  // Create the 'hui-picture-entity' card dynamically
  const element = await cardHelpers.createCardElement(config);

  // Assign the hass object to the card
  element.hass = instance._hass;

  // Render the card in the DOM
  const container = instance.shadowRoot.querySelector(selector);
  container.innerHTML = ""; // Clear previous content
  container.appendChild(element);

  // Ensure the card updates completely
  await element.updateComplete;
}

export async function updateCard(changedProperties, selector, instance) {
  {
    if (changedProperties.has("hass")) {
      const container = instance.shadowRoot.querySelector(selector);
      if (container && container.firstChild) {
        container.firstChild.hass = instance._hass; // Update the hass property of the card
      }
    }
  }
}

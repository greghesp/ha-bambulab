# 🐼 Bambu Lab Cards

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![build][build-badge]

The Bambu Lab Cards, are a set of pre-made collection of cards for Home Assistant. Designed to work with the Bambu Lab Home Assistant Integration

They are currently a work in progress

## Installation

### Prerequisites

- Install the [Bambu Lab Integration](https://github.com/greghesp/ha-bambulab)

### HACS

Bambu Lab Cards are available in [HACS][hacs] (Home Assistant Community Store).

Use this link to directly go to the repository in HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=greghesp&repository=ha-bambulab-cards)

## Usage

All the cards can be configured using Dashboard UI editor.

1. In Dashboard UI, click 3 dots in top right corner.
2. Click _Edit Dashboard_.
3. Click Plus button to add a new card.
4. Find one of the _Custom: Bambu_ card in the list.

### Cards

- [AMS Card](docs/cards/ams-card.md)

### Development

1. Clone this repo
2. Setup a local instance of Home Assistant, I prefer to use Docker for this
3. Install the [Bambu Lab Integration](https://github.com/greghesp/ha-bambulab)
4. Setup a docker-compose.yml file with the correct volume binds. My file as an example:

```yml
version: "3.3"
services:
  hass:
    image: homeassistant/home-assistant:beta
    container_name: homeassistant
    restart: unless-stopped # To reboot the container when the host comes back up from restarts.
    ports:
      - 8123:8123
    volumes:
      - type: bind
        source: ../custom/ha-bambulab-cards/dist
        target: /config/www/community/ha-bambulab-cards
      - ./hass_dev:/config
```

<!-- Badges -->

[hacs-url]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/hacs-custom-orange.svg?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/greghesp/ha-bambulab-cards?style=flat-square
[release-url]: https://github.com/greghesp/ha-bambulab-cards/releases
[build-badge]: https://img.shields.io/github/actions/workflow/status/greghesp/ha-bambulab-cards/build.yaml?branch=main&style=flat-square
[hacs]: https://hacs.xyz

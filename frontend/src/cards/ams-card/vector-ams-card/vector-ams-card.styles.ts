import { css } from "lit";

export default css`
  :root {
    --light-reflection-color-low: rgba(255, 255, 255, 0);
    --light-reflection-color-high: rgba(255, 255, 255, 0.2);
  }

  .v-extra-info {
    display: flex;
    flex-wrap: nowrap;
    justify-content: flex-end;
    column-gap: 10px;
    padding: 2% 4%;
  }

  .v-info {
    background: #4f4f4f;
    padding: 0.5em;
    border-radius: 0.5em;
    color: white;
    font-size: smaller;
  }

  .v-ams-container {
    border-radius: 5px;
    display: flex;
    flex-wrap: nowrap;
    justify-content: space-evenly;
    padding: 0% 2% 5% 2%;
  }

  .v-spool-holder {
    border: 0.5rem solid #808080;
    background: linear-gradient(#959595, #626262, #959595);
    border-radius: 0.6em;
    width: 20%;
    display: flex;
    position: relative;
    min-height: 130px;
  }

  .v-spool-info {
    position: absolute;
    z-index: 2;
    background: #444444;
    padding: 8%;
    border-radius: 0.5em;
    bottom: -15%;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    color: white;
    font-size: small;
  }
`;

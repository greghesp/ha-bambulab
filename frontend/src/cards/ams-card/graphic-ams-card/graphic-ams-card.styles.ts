import { css } from "lit";

export default css`
  .ams-container {
    height: 100%;
    width: 100%;
    position: relative;
  }

  .ams-container img {
    display: block;
    width: 100%;
    height: auto;
  }

  .spool {
    position: absolute;
    z-index: 1;
    top: 0;
    height: 100%;
    width: 14%;
    display: flex;
    justify-content: space-evenly;
    flex-direction: column;
  }

  .spool-info {
    height: 50%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }

  .ams-container .humidity {
    top: 36%;
    text-align: center;
    font-size: 1em;
    background-color: rgba(0, 0, 0);
    border-radius: 50px;
    padding: 8px;
    pointer-events: none;
    position: absolute;
    z-index: 2;
    left: 90%;
    width: 30px;
  }

  .ams-container .ams-temperature {
    top: 60%;
    text-align: center;
    font-size: 0.6em;
    background-color: rgba(0, 0, 0);
    border-radius: 50px;
    padding: 8px;
    pointer-events: none;
    position: absolute;
    z-index: 2;
    left: 90%;
    width: 30px;
    color: white;
  }

  .ams-container .spool-badge {
    top: 20%;
    text-align: center;
    font-size: 1em;
    background-color: rgba(0, 0, 0, 0.4);
    border-radius: 50px;
    padding: 8px;
    pointer-events: none;
    position: absolute;
    z-index: 2;
  }

  .slot-1 {
    left: 15%;
  }

  .slot-2 {
    left: 32.5%;
  }

  .slot-3 {
    left: 52.7%;
  }

  .slot-4 {
    left: 72%;
  }

  .ams-container .spool-type {
    color: white;
    text-align: center;
    padding: 8px;
    font-size: 1em;
    background-color: rgba(0, 0, 0, 0.4);
    border-radius: 5px;
    pointer-events: none;
    position: absolute;
    z-index: 2;
    margin-top: 25%;
  }

  .extra-info {
    display: flex;
    flex-wrap: nowrap;
    justify-content: center;
    align-items: center;
    column-gap: 10px;
    padding: 2% 4%;
  }

  .subtitle {
    width: 50%;
  }

  .info-slots {
    display: flex;
    flex-wrap: nowrap;
    justify-content: flex-end;
    column-gap: 10px;
    width: 50%;
  }

  .info {
    background: #4f4f4f;
    padding: 0.5em;
    border-radius: 0.5em;
    color: white;
    font-size: smaller;
  }
`;

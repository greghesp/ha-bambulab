import { css } from "lit";

export default css`
  :host {
    display: block;
    width: 100%;
    box-sizing: border-box;
  }

  .v-spool {
    background: #3d3d3d;
    width: 15%;
    height: 100%;
  }

  .v-spool-container {
    padding: 15% 0;
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
    box-sizing: border-box;
    border: 2px solid #5a5a5a;
    border-radius: 3px;
  }

  .v-string-roll {
    position: relative;
    width: 100%; /* Width of the roll */
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #4160bf;
    flex-grow: 1;
    box-sizing: border-box;
  }

  .v-string-layer {
    position: absolute;
    width: 2px; /* Thickness of each vertical string line */
    height: 100%; /* Full height of the roll */
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 2;
  }

  .v-reflection {
    width: 100%;
    height: 100%;
    animation: lightReflection 3s linear infinite; /* Animation for the moving light reflection */
  }

  @keyframes lightReflection {
    0% {
      background: linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0) 10%,
        rgba(255, 255, 255, 0.2) 50%,
        rgba(255, 255, 255, 0) 90%
      );
      background-size: 100% 50%;
      background-position: 0 0;
    }
    50% {
      background: linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0) 10%,
        rgba(255, 255, 255, 0.2) 50%,
        rgba(255, 255, 255, 0) 90%
      );
      background-size: 100% 100%;
      background-position: 0 50%;
    }
    100% {
      background: linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0) 10%,
        rgba(255, 255, 255, 0.2) 50%,
        rgba(255, 255, 255, 0) 90%
      );
      background-size: 100% 50%;
      background-position: 0 100%;
    }
  }

  .string-roll-container {
    max-height: 100%;
    min-height: 10%;
    height: 100%;
    box-sizing: border-box;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .remaining-percent {
    width: 100%;
    height: 100%;
    z-index: 3;
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: small;
  }

  .remaining-percent p {
    background: #0000008c;
    padding: 0.2em;
    border-radius: 0.3em;
    color: white;
  }

  @keyframes wiggle {
    0% {
      transform: skew(0deg, 0deg);
    }
    10% {
      transform: skew(2deg, 2deg);
    }
    20% {
      transform: skew(0deg, 0deg);
    }
    30% {
      transform: skew(-2deg, -2deg);
    }
    40% {
      transform: skew(0deg, 0deg);
    }
    50% {
      transform: skew(2deg, 2deg);
    }
    60% {
      transform: skew(0deg, 0deg);
    }
    70% {
      transform: skew(-2deg, -2deg);
    }
    80% {
      transform: skew(0deg, 0deg);
    }
  }
`;

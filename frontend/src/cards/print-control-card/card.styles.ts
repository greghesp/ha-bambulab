import { css } from "lit";

export default css`
  /* Styling for the 'alpha' text */
  .alpha-text {
    position: absolute; /* Position it absolutely within the card */
    top: 10px;           /* 10px from the top */
    right: 10px;         /* 10px from the right */
    color: red;          /* Red text */
    font-size: 18px;     /* Adjust font size */
    font-weight: bold;   /* Optional: make the text bold */
  }
  .button {
    padding: 4px 8px;
    font-size: 16px;
    background-color: var(--primary-color);
    color: white;
    border: none;
    cursor: pointer;
  }
  button:disabled {
    background-color: #ccc;  /* Light grey background when disabled */
    color: #666;  /* Dark grey text */
    cursor: not-allowed;  /* Change cursor to indicate it's not clickable */
  }
  .button-container {
    display: flex;
    justify-content: flex-end;  /* This will align the buttons to the right */
    gap: 10px;  /* Optional: Adds space between buttons */
  }
  .canvas {
    display: block;
  }
  .card {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 16px;
    background: var(--card-background-color);
  }
  .popup {
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: white;
    padding: 20px;
    border: 1px solid #ccc;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
    z-index: 1000;
  }
  .popup-background {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }
  .popup-header {
    font-size: 18px;
    margin-bottom: 10px;
    color: black; /* Ensure the header text is black */
  }
  .popup-content {
    font-size: 14px;
    color: black; /* Ensure the content text is black */
  }
  /* Remove bullets from the list */
  #checkboxList {
    list-style-type: none;
    padding: 0;
  }
  /* Style the checkbox list items */
  #checkbox li {
    margin: 10px 0;
  }
`;
export function getContrastingTextColor(hexColor) {
  // Remove the '#' if present
  hexColor = hexColor.replace("#", "");

  // Convert the hex color to RGB
  let r = parseInt(hexColor.substring(0, 2), 16);
  let g = parseInt(hexColor.substring(2, 4), 16);
  let b = parseInt(hexColor.substring(4, 6), 16);

  // Calculate the luminance of the color
  let luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;

  // If luminance is greater than 128, the color is light, so we return black text, otherwise white
  return luminance > 128 ? "#000000" : "#FFFFFF";
}

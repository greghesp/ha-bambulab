declare module "*.png" {
  const content: string; // This tells TypeScript to treat PNG files as strings (the URL/path of the image)
  export default content;
}

declare module "*.svg" {
  const content: string; // or 'React.Component<React.SVGProps<SVGSVGElement>>' if you're using React
  export default content;
}

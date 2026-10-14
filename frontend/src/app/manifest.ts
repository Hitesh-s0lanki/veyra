import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Veyra — AI Video Generator",
    short_name: "Veyra",
    description: "Imagine it. See it move. Create AI videos from text and images.",
    start_url: "/",
    display: "standalone",
    background_color: "#090F29",
    theme_color: "#090F29",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}

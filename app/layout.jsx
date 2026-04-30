import { Outfit, Public_Sans } from "next/font/google";
import "./globals.css";

const publicSans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-public-sans",
  weight: ["400", "500", "600", "700"]
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  weight: ["500", "600", "700"]
});

export const metadata = {
  title: "VILO Dashboard",
  description: "Sidebar-first dashboard shell"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${publicSans.variable} ${outfit.variable}`}>
      <body>{children}</body>
    </html>
  );
}

import "./globals.css";

export const metadata = {
  title: "VILO Dashboard",
  description: "Sidebar-first dashboard shell"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
export const metadata: Metadata = { title: "ModelVerse — AI Engineering Workspace", description: "From business problem to production-ready AI solutions. ModelVerse is your intelligent AI solution engineering platform." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}><body>{children}</body></html>; }

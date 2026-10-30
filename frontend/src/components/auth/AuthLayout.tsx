import React from "react";
import { Link } from "react-router-dom";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  footerPrompt: string;
  footerLinkText: string;
  footerLinkTo: string;
  children: React.ReactNode;
}

export function AuthLayout({
  title,
  subtitle,
  footerPrompt,
  footerLinkText,
  footerLinkTo,
  children,
}: AuthLayoutProps) {
  return (
    <main
      className="min-h-screen w-full relative flex items-center justify-center p-4 sm:p-6 lg:p-8 overflow-x-hidden bg-cover bg-center bg-no-repeat selection:bg-stone-900 selection:text-white"
      style={{
        backgroundImage: "url('/assets/misty-forest-bg.jpg')",
      }}
    >
      {/* Subtle darkening vignette layer to ensure maximum contrast and depth */}
      <div className="absolute inset-0 bg-black/15 pointer-events-none" />

      {/* Main Centered Authentication Panel */}
      <section className="relative z-10 w-full max-w-[920px] my-auto bg-white rounded-[28px] sm:rounded-[32px] border border-white/60 sm:border-stone-200/90 shadow-[0_25px_70px_rgba(0,0,0,0.32)] overflow-hidden flex flex-col md:flex-row min-h-[560px]">
        {/* Left Column: Interactive Authentication Form */}
        <div className="w-full md:w-[50%] lg:w-[48%] p-6 sm:p-8 md:p-10 flex flex-col justify-between bg-white z-10">
          <div>
            {/* Minimal Geometric Logo */}
            <div className="flex items-center mb-4 sm:mb-5">
              <svg
                className="w-5 h-5 sm:w-6 sm:h-6 text-black"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-label="Brand Logo"
              >
                <path d="M4 17L10 3h3L7 17H4z" />
                <path d="M11 21L17 7h3l-6 14h-3z" />
              </svg>
            </div>

            {/* Header Titles */}
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
              {title}
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-neutral-500 font-normal">
              {subtitle}
            </p>

            {/* Dynamic Form Content */}
            <div className="mt-4 sm:mt-5">{children}</div>
          </div>

          {/* Footer Link */}
          <div className="mt-6 pt-2 text-center text-xs sm:text-sm text-neutral-500">
            {footerPrompt}{" "}
            <Link
              to={footerLinkTo}
              className="font-semibold text-neutral-900 underline underline-offset-4 hover:text-black transition-colors"
            >
              {footerLinkText}
            </Link>
          </div>
        </div>

        {/* Right Column: Exact Halftone Artwork Reused Directly from Reference */}
        <div className="hidden md:flex md:w-[50%] lg:w-[52%] relative bg-white items-center justify-end overflow-hidden border-l border-stone-100/60">
          <img
            src="/assets/halftone-artwork.png"
            alt="Authentic Halftone Artwork"
            className="w-full h-full object-cover object-right pointer-events-none select-none"
          />
        </div>
      </section>
    </main>
  );
}

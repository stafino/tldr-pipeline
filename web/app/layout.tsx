import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });

const SITE_URL = 'https://www.trylede.com';
const TITLE = 'TLDR newsletter curator tool';
const DESCRIPTION =
  'AI-assisted curation for the TLDR family of newsletters. Score, blurb and ship in minutes.';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    template: '%s · TLDR curator',
  },
  description: DESCRIPTION,
  applicationName: 'lede',
  manifest: '/manifest.webmanifest',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: 'lede',
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
  },
};

export const viewport: Viewport = {
  themeColor: '#0E0E10',
};

const JSON_LD = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      url: `${SITE_URL}/`,
      name: 'lede',
      description: 'AI-assisted curation pipeline for the TLDR family of newsletters.',
    },
    {
      '@type': 'SoftwareApplication',
      name: 'lede',
      applicationCategory: 'BusinessApplication',
      operatingSystem: 'Web',
      description: 'Score, blurb and assemble the next TLDR edition.',
      url: `${SITE_URL}/`,
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans bg-bg text-text">
        {children}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
      </body>
    </html>
  );
}

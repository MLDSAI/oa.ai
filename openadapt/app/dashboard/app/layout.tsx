import './globals.css'

import { ColorSchemeScript, MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { Shell } from '@/components/Shell'
import { CSPostHogProvider } from './providers'
import { Poppins } from 'next/font/google'

const poppins = Poppins({
    subsets: ['latin'],
    weight: ['400', '700'],
})

export const metadata = {
    title: 'OpenAdapt.AI',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <head>
                <ColorSchemeScript />
            </head>
            <CSPostHogProvider>
                <body className={poppins.className}>
                    <MantineProvider>
                        <Notifications />
                        <Shell>{children}</Shell>
                    </MantineProvider>
                </body>
            </CSPostHogProvider>
        </html>
    )
}

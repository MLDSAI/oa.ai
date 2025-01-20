'use client'

import { AppShell, Box, Burger, Image, Text } from '@mantine/core'
import React from 'react'
import { Navbar } from '../Navbar'
import { usePathname } from 'next/navigation'
import { useDisclosure } from '@mantine/hooks'
import logo from '../../../assets/logo_inverted.png'

type Props = {
    children: React.ReactNode
}

export const Shell = ({ children }: Props) => {
    const pathname = usePathname()
    const isRecordingDetails = pathname?.includes('/recordings/detail')
    return (
        <AppShell
            navbar={{
                width: 300,
                breakpoint: 'sm',
            }}
            padding="md"
            withBorder
        >
            <AppShell.Navbar className=" bg-[radial-gradient(circle_at_center,_rgb(15,23,42),_rgb(2,6,23))] p-4 z-0">
                <Box className="p-4">
                    <Box className="flex items-center gap-x-2 mb-6">
                        <Image src={logo.src} alt="OpenAdapt" w={40} />
                        <Text className="text-white text-xl">OpenAdapt.AI</Text>
                    </Box>
                </Box>
                <Navbar />
            </AppShell.Navbar>

            <AppShell.Main
                className={
                    isRecordingDetails
                        ? 'bg-slate-100'
                        : 'bg-[radial-gradient(circle_at_center,_rgb(191,219,254),_rgb(255,237,213))]'
                }
            >
                {children}
            </AppShell.Main>
        </AppShell>
    )
}

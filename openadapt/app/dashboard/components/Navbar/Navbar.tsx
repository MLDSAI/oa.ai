'use client'

import { usePathname } from 'next/navigation'
import { routes } from '@/app/routes'
import Link from 'next/link'
import React from 'react'
import { IconChevronRight } from '@tabler/icons-react'

export const Navbar = () => {
    const currentRoute = usePathname()

    return (
        <div className="p-4 bg-secondary/30 backdrop-blur-md backdrop-saturate-150 border border-white/20 shadow-lg rounded-lg">
            {routes.map((route) => (
                <Link href={route.path} key={route.path} passHref>
                    <div
                        className={`
                            flex items-center p-3 rounded-md transition-all transform group
                            ${
                                currentRoute.includes(route.path)
                                    ? 'bg-primary text-zinc-300'
                                    : 'text-zinc-300'
                            }
                            hover:scale-105 hover:bg-blue-600/30 hover:text-white
                        `}
                    >
                        <route.icon
                            size={20}
                            className={`
                                mr-3 transition-transform duration-200
                                ${
                                    currentRoute.includes(route.path)
                                        ? 'text-blue-400'
                                        : 'text-gray-400 group-hover:text-white'
                                }
                            `}
                            stroke={1.5}
                        />
                        <span className="flex-1">{route.name}</span>
                        <IconChevronRight
                            size={18}
                            className={`
                                ml-2 transition-transform duration-200
                                ${
                                    currentRoute.includes(route.path)
                                        ? 'text-blue-400'
                                        : 'text-gray-400 group-hover:text-white'
                                }
                                group-hover:translate-x-2
                            `}
                            stroke={1.5}
                        />

                        {route.badge && (
                            <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-300">
                                {route.badge}
                            </span>
                        )}
                    </div>
                </Link>
            ))}
        </div>
    )
}

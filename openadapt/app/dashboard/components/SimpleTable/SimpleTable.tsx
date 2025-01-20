import { Button, Flex, Table } from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import React from 'react'

type Props<T extends Record<string, any>> = {
    columns: {
        name: string
        accessor: string | ((row: T) => React.ReactNode)
    }[]
    data: T[]
    refreshData: () => void
    onClickRow: (
        row: T
    ) => (event: React.MouseEvent<HTMLTableRowElement, MouseEvent>) => void
}

export function SimpleTable<T extends Record<string, any>>({
    columns,
    data,
    refreshData,
    onClickRow,
}: Props<T>) {
    return (
        <Flex
            direction="column"
            mt={20}
            align="flex-end"
            className="w-full max-w-screen-xl mx-auto px-4"
        >
            <Button
                w="fit-content"
                leftSection={<IconRefresh />}
                variant="outline"
                onClick={refreshData}
                className="hover:bg-accent bg-primary/80 hover:text-zinc-100 text-zinc-200 hover:text-white"
            >
                Refresh
            </Button>
            <Table
                withTableBorder
                mt={20}
                align="center"
                className="bg-zinc-100 shadow-xl rounded-xl min-w-full overflow-x-auto whitespace-nowrap transition-all duration-300 ease-in-out
                hover:shadow-[0_0_15px_rgba(59,130,246,0.5)]
                hover:border-blue-400
                group"
            >
                <Table.Thead>
                    <Table.Tr>
                        {columns.map(({ name }) => (
                            <Table.Th
                                className="whitespace-nowrap bg-gray-50 rounded-md py-4 text-md font-semibold text-gray-900"
                                key={name}
                            >
                                {name}
                            </Table.Th>
                        ))}
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {data.map((row, rowIndex) => (
                        <Table.Tr
                            key={rowIndex}
                            className="group/row hover:cursor-pointer hover:bg-blue-100/70
                       group-hover:border-blue-200
                       transition-colors duration-200"
                            onClick={onClickRow(row)}
                        >
                            {columns.map(
                                (
                                    { accessor, name: columnName },
                                    accesorIndex
                                ) => (
                                    <Table.Td
                                        key={accesorIndex}
                                        py={20}
                                        className={`${columnName === 'Video' ? 'opacity-80 group-hover/row:opacity-100 transition-opacity duration-300' : ''}`}
                                    >
                                        {typeof accessor === 'string'
                                            ? row[accessor]
                                            : accessor(row)}
                                    </Table.Td>
                                )
                            )}
                        </Table.Tr>
                    ))}
                </Table.Tbody>
            </Table>
        </Flex>
    )
}

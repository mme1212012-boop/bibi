package com.bibi.android

data class Tube(val colors: MutableList<Int>)

data class Move(val from: Int, val to: Int, val amount: Int)

object WaterSortSolver {
    fun solve(start: List<List<Int>>, capacity: Int = 4): List<Move> {
        val initial = start.map { it.toList() }
        val visited = mutableMapOf<String, Pair<List<List<Int>>, Move?>>()
        val queue: ArrayDeque<List<List<Int>>> = ArrayDeque()
        queue.add(initial)
        visited[stateKey(initial)] = initial to null

        while (queue.isNotEmpty()) {
            val state = queue.removeFirst()
            if (isSolved(state, capacity)) {
                val result = mutableListOf<Move>()
                var key = stateKey(state)
                while (true) {
                    val entry = visited[key] ?: break
                    val move = entry.second ?: break
                    result.add(move)
                    val previous = entry.first
                    key = stateKey(previous)
                }
                return result.asReversed()
            }

            for (from in state.indices) {
                if (state[from].isEmpty()) continue
                val color = state[from].last()
                var amount = 1
                for (index in state[from].size - 2 downTo 0) {
                    if (state[from][index] == color) amount++ else break
                }

                for (to in state.indices) {
                    if (from == to || state[to].size >= capacity) continue
                    if (state[to].isNotEmpty() && state[to].last() != color) continue
                    if (state[to].isEmpty() && amount == state[from].size) continue

                    val amountToMove = minOf(amount, capacity - state[to].size)
                    val next = state.map { it.toMutableList() }.toMutableList()
                    repeat(amountToMove) { next[to].add(next[from].removeLast()) }
                    val nextKey = stateKey(next)
                    if (nextKey in visited) continue
                    val move = Move(from, to, amountToMove)
                    visited[nextKey] = state to move
                    queue.add(next)
                }
            }
        }
        return emptyList()
    }

    private fun isSolved(state: List<List<Int>>, capacity: Int): Boolean =
        state.all { tube ->
            tube.isEmpty() ||
                (tube.size == capacity && tube.all { color -> color == tube.first() })
        }

    private fun stateKey(state: List<List<Int>>): String =
        state.joinToString("|") { tube -> tube.joinToString(",") { it.toString() } }
}

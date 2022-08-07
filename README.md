# dbdiag

Diagrams as text tools for databases and distributed systems

## ophistory

This tool is used to make diagrams for showing concurrent operations, modeled after those seen in [Linearizability: A corretness condition for concurrent objects](https://cs.brown.edu/~mph/HerlihyW90/p463-herlihy.pdf).

It may be invoked as `ophistory.py <input_file> -o <output_file.svg>`.

The input file follows a similar syntax as the paper as well.  Each line has three parts:

`<ACTOR> [:.]? <OPERATION> [KEY]`

Where `<>` is required and `[]` is optional.

The `ACTOR` exists to group spans together.  It should either be the object being operated upon, on the entity performing the operations.  `OPERATION` is the text that will be displayed above a span.  If the text has spaces, but double quotes around it.  `KEY` can be any identifier, and the first time that a key is seen on a line, the line is interpreted as the start of the span.  The next line with the same `KEY` denotes the end of the span, and then the `KEY` is forgotten.

The operation `END` is special, and not displayed.  The span will be shown with just one operation text centered over the span instead.  If an operation starts and immediately finishes, you may omit the `KEY`.  This is semantically equivlent to writing an immediately following line with an `END` operation.

To reproduce the four FIFO queue histories from _S1.2 Motivation_:

<table>
<tbody>
<tr>
  <td>

<pre><code>
A: E(x) a
B: E(y)
A: END a
B: D(x)
A: D(y)
A: E(z)
</code></pre>
  </td>
  <td><img src="examples/linearizability_1.2.a.svg" /></td>
</tr>
  <td>
<pre><code>
A: E(x)
B: E(y) a
A: D(y) a
B: END a
A: END a
</code></pre>
  </td>
  <td><img src="examples/linearizability_1.2.b.svg" /></td>
</tr>
  <td>
<pre><code>
A: E(x) a
B: D(x)
A: END a
</code></pre>
  </td>
  <td><img src="examples/linearizability_1.2.c.svg" /></td>
</tr>
  <td>
<pre><code>
A: E(x) a
B: E(y) a
A: END a
B: END a
A: D(y) a
C: D(x) a
A: END a
C: END a
</code></pre>
  </td>
  <td><img src="examples/linearizability_1.2.d.svg" /></td>
</tr>
</tbody>
</table>


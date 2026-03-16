function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Claude Explorer</h1>
        <p className="text-sm text-gray-500 mt-1">
          .claude/ configuration visualizer
        </p>
      </header>
      <main className="flex items-center justify-center h-[calc(100vh-5rem)]">
        <div className="text-center">
          <p className="text-lg text-gray-600">
            Claude Explorer is loading...
          </p>
          <p className="text-sm text-gray-400 mt-2">
            Components will be displayed here.
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;

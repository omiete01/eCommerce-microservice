import React, { useEffect, useState } from 'react';

function App() {
  const [users, setUsers] = useState([]);
  const [products, setProducts] = useState([]);
  const [newUser, setNewUser] = useState('');
  const [newProduct, setNewProduct] = useState('');

  const fetchUsers = async () => {
    const res = await fetch('http://localhost:5001/users');
    const data = await res.json();
    setUsers(data);
  };

  const fetchProducts = async () => {
    const res = await fetch('http://localhost:5002/products');
    const data = await res.json();
    setProducts(data);
  };

  useEffect(() => {
    fetchUsers();
    fetchProducts();
  }, []);

  const handleAddUser = async (e) => {
    e.preventDefault();
    await fetch('http://localhost:5001/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newUser }),
    });
    setNewUser('');
    fetchUsers();
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    await fetch('http://localhost:5002/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newProduct }),
    });
    setNewProduct('');
    fetchProducts();
  };

  return (
    <div className="container mt-4">
      <h1 className="text-center mb-4">eCommerce Dashboard</h1>

      <div className="row">
        {/* Users */}
        <div className="col-md-6">
          <h3>Users</h3>
          <form onSubmit={handleAddUser} className="mb-3">
            <div className="input-group">
              <input
                type="text"
                value={newUser}
                onChange={(e) => setNewUser(e.target.value)}
                className="form-control"
                placeholder="New user name"
              />
              <button type="submit" className="btn btn-primary">Add</button>
            </div>
          </form>
          <ul className="list-group">
            {users.map((user) => (
              <li key={user.id} className="list-group-item">
                {user.name}
              </li>
            ))}
          </ul>
        </div>

        {/* Products */}
        <div className="col-md-6">
          <h3>Products</h3>
          <form onSubmit={handleAddProduct} className="mb-3">
            <div className="input-group">
              <input
                type="text"
                value={newProduct}
                onChange={(e) => setNewProduct(e.target.value)}
                className="form-control"
                placeholder="New product name"
              />
              <button type="submit" className="btn btn-success">Add</button>
            </div>
          </form>
          <ul className="list-group">
            {products.map((product) => (
              <li key={product.id} className="list-group-item">
                {product.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default App;

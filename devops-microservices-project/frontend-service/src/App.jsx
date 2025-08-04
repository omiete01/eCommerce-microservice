import React, { useState, useEffect } from 'react';

function App() {
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [products, setProducts] = useState([]);

  const loggedIn = !!token;

  useEffect(() => {
    if (token) {
      fetchProducts();
    }
  }, [token]);

  const handleLogin = async () => {
    const res = await fetch('http://localhost:5001/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, password }),
    });

    const data = await res.json();
    if (data.token) {
      localStorage.setItem('token', data.token);
      setToken(data.token);
    } else {
      alert(data.error || 'Login failed');
    }
  };

  const handleRegister = async () => {
    const res = await fetch('http://localhost:5001/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, password }),
    });

    const data = await res.json();
    if (res.status === 201) {
      alert('Registration successful! You can now log in.');
      setIsLogin(true);
    } else {
      alert(data.error || 'Registration failed');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    isLogin ? await handleLogin() : await handleRegister();
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setName('');
    setPassword('');
  };

  const fetchProducts = async () => {
    const res = await fetch('http://localhost:5002/products');
    const data = await res.json();
    setProducts(data);
  };

  return (
    <div className="container mt-5">
      {!loggedIn ? (
        <div className="col-md-6 offset-md-3">
          <div className="text-center mb-4">
            <button className={`btn btn-sm ${isLogin ? 'btn-primary' : 'btn-outline-primary'} me-2`}
              onClick={() => setIsLogin(true)}>
              Login
            </button>
            <button className={`btn btn-sm ${!isLogin ? 'btn-success' : 'btn-outline-success'}`}
              onClick={() => setIsLogin(false)}>
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <h3 className="text-center">{isLogin ? 'Login' : 'Register'}</h3>
            <div className="mb-3">
              <input
                type="text"
                placeholder="Username"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="form-control"
                required
              />
            </div>
            <div className="mb-3">
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="form-control"
                required
              />
            </div>
            <button type="submit" className="btn btn-block w-100 btn-dark">
              {isLogin ? 'Login' : 'Register'}
            </button>
          </form>
        </div>
      ) : (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2>Product Dashboard</h2>
            <button onClick={handleLogout} className="btn btn-outline-danger">
              Logout
            </button>
          </div>
          <ul className="list-group">
            {products.map((product) => (
              <li key={product.id} className="list-group-item">
                {product.name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;

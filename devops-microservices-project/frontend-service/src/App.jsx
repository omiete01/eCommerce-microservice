// FRONTEND - React App
import React, { useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode'; 

const apiUserUrl = import.meta.env.VITE_USER_API_URL;
const apiProductUrl = import.meta.env.VITE_PRODUCT_API_URL;

function App() {
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [products, setProducts] = useState([]);
  const [productName, setProductName] = useState('');
  const [productPrice, setProductPrice] = useState('');
  const [productDescription, setProductDescription] = useState('');
  const [editingProductId, setEditingProductId] = useState(null);
  const [userId, setUserId] = useState(null);
  const loggedIn = !!token;

  // Extract user ID from token
  const extractUserIdFromToken = (token) => {
    if (!token) return null;
    try {
      const decoded = jwtDecode(token);
      console.log('Decoded token:', decoded); // Debug log
      // Try multiple possible field names
      return decoded.user_id || decoded.userId || decoded.id || decoded.sub || null;
    } catch (error) {
      console.error('Error decoding token:', error);
      return null;
    }
  };

  // Initialize user ID from existing token
  useEffect(() => {
    if (token) {
      const id = extractUserIdFromToken(token);
      setUserId(id);
    }
  }, [token]);

  // Fetch products when logged in
  useEffect(() => {
    if (token && userId) {
      fetchProducts();
    }
  }, [token, userId]);

  const handleLogin = async () => {
    const res = await fetch(`${apiUserUrl}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, password }),
    });

    const data = await res.json();
    if (data.token) {
      localStorage.setItem('token', data.token);
      setToken(data.token);
      
      // Extract and set user ID from new token
      const id = extractUserIdFromToken(data.token);
      setUserId(id);
      
      if (!id) {
        console.warn('User ID not found in token. Token structure:', jwtDecode(data.token));
        alert('Login successful but user ID not found in token. Please check token structure.');
      }
    } else {
      alert(data.error || 'Login failed');
    }
  };

  const handleRegister = async () => {
    const res = await fetch(`${apiUserUrl}/register`, {
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
    setUserId(null);
    setName('');
    setPassword('');
    setProductName('');
    setProductPrice('');
    setProductDescription('');
    setEditingProductId(null);
    setProducts([]);
  };

  const fetchProducts = async () => {
    try {
      const res = await fetch(`${apiProductUrl}/products`, {
        headers: {
          'Authorization': `Bearer ${token}` 
        }
      });
      const data = await res.json();
      setProducts(data);
    } catch (error) {
      console.error('Error fetching products:', error);
      alert('Failed to fetch products');
    }
  };

  const handleProductSubmit = async (e) => {
    e.preventDefault();

    const trimmedName = productName.trim();
    const trimmedDesc = productDescription.trim();
    const priceValue = parseFloat(productPrice);

    if (!trimmedName || isNaN(priceValue) || priceValue <= 0) {
      alert('Name and valid price are required');
      return;
    }
    
    // Check if user ID is available
    if (!userId) {
      alert('User ID is required to create a product. Please log in again.');
      console.log('Current token:', token);
      console.log('Current userId:', userId);
      return;
    }

    const product = {
      name: trimmedName,
      price: priceValue,
      description: trimmedDesc,
      user_id: userId,
    };

    try {
      let res;
      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` // Add auth header if needed
      };

      if (editingProductId) {
        res = await fetch(`${apiProductUrl}/products/${editingProductId}`, {
          method: 'PUT',
          headers,
          body: JSON.stringify(product),
        });
      } else {
        res = await fetch(`${apiProductUrl}/products`, {
          method: 'POST',
          headers,
          body: JSON.stringify(product),
        });
      }

      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Something went wrong');
        return;
      }

      setProductName('');
      setProductPrice('');
      setProductDescription('');
      setEditingProductId(null);
      fetchProducts();
    } catch (err) {
      console.error(err);
      alert('Unexpected error');
    }
  };

  const handleEdit = (product) => {
    setProductName(product.name);
    setProductPrice(product.price.toString());
    setProductDescription(product.description || '');
    setEditingProductId(product.id);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this product?')) return;

    try {
      await fetch(`${apiProductUrl}/products/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}` // Add auth header if needed
        }
      });
      fetchProducts();
    } catch (error) {
      console.error('Error deleting product:', error);
      alert('Failed to delete product');
    }
  };

  return (
    <div className="container mt-5">
      {!loggedIn ? (
        <div className="col-md-6 offset-md-3">
          <div className="text-center mb-4">
            <button className={`btn btn-sm ${isLogin ? 'btn-primary' : 'btn-outline-primary'} me-2`} onClick={() => setIsLogin(true)}>Login</button>
            <button className={`btn btn-sm ${!isLogin ? 'btn-success' : 'btn-outline-success'}`} onClick={() => setIsLogin(false)}>Register</button>
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
            <div>
              <small className="me-3">User ID: {userId || 'Not found'}</small>
              <button onClick={handleLogout} className="btn btn-outline-danger">Logout</button>
            </div>
          </div>

          <form onSubmit={handleProductSubmit} className="mb-4">
            <h5>{editingProductId ? 'Edit Product' : 'Add Product'}</h5>
            <div className="row g-2 mb-2">
              <div className="col-md-4">
                <input 
                  type="text" 
                  className="form-control" 
                  placeholder="Product Name" 
                  value={productName} 
                  onChange={(e) => setProductName(e.target.value)} 
                  required 
                />
              </div>
              <div className="col-md-3">
                <input 
                  type="number" 
                  className="form-control" 
                  placeholder="Price" 
                  value={productPrice} 
                  onChange={(e) => setProductPrice(e.target.value)} 
                  step="0.01" 
                  required 
                />
              </div>
              <div className="col-md-5">
                <input 
                  type="text" 
                  className="form-control" 
                  placeholder="Description" 
                  value={productDescription} 
                  onChange={(e) => setProductDescription(e.target.value)} 
                />
              </div>
            </div>
            <button type="submit" className="btn btn-success">
              {editingProductId ? 'Update' : 'Add'}
            </button>
          </form>

          <ul className="list-group">
            {products.map((product) => (
              <li key={product.id} className="list-group-item d-flex justify-content-between align-items-center">
                <div>
                  <strong>{product.name}</strong> — ${product.price.toFixed(2)}<br />
                  <small>{product.description}</small>
                  <br />
                  <small>Created by: {product.creator || product.user_id}</small>
                </div>
                <div>
                  <button onClick={() => handleEdit(product)} className="btn btn-sm btn-warning me-2">Edit</button>
                  <button onClick={() => handleDelete(product.id)} className="btn btn-sm btn-danger">Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;
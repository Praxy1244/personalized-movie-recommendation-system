$(function () {
  // Button will be disabled until input has some value
  const source = document.getElementById('autoComplete');
  const inputHandler = function (e) {
    if (e.target.value === "") {
      $('.movie-button').attr('disabled', true);
    } else {
      $('.movie-button').attr('disabled', false);
    }
  };
  source.addEventListener('input', inputHandler);

  $('.movie-button').on('click', function () {
    const myApiKey = '351aef8735cc66f2cd77af1e485fd71c'; // Replace with your TMDB API Key
    const title = $('.movie').val();

    if (title === "") {
      $('.results').css('display', 'none');
      $('.fail').css('display', 'block');
    } else {
      loadDetails(myApiKey, title);
    }
  });
});

// Trigger recommendation card click
function recommendcard(e) {
  const myApiKey = '351aef8735cc66f2cd77af1e485fd71c'; // Replace with your TMDB API Key
  const title = e.getAttribute('title');
  loadDetails(myApiKey, title);
}

// Fetch basic movie details by title
async function loadDetails(myApiKey, title) {
  try {
    const response = await fetch(`https://api.themoviedb.org/3/search/movie?api_key=${myApiKey}&query=${title}`);
    const movie = await response.json();

    if (movie.results.length < 1) {
      $('.fail').css('display', 'block');
      $('.results').css('display', 'none');
      $("#loader").fadeOut();
    } else {
      $("#loader").fadeIn();
      $('.fail').css('display', 'none');
      $('.results').css('display', 'block');

      const movieId = movie.results[0].id;
      const movieTitle = movie.results[0].original_title;

      await movieRecs(movieTitle, movieId, myApiKey);
    }
  } catch (error) {
    console.error('Failed to fetch movie details:', error);
    alert('Error fetching movie details.');
    $("#loader").fadeOut();
  }
}

// Get movie recommendations from Flask backend
async function movieRecs(movieTitle, movieId, myApiKey) {
  try {
    const response = await $.post("/similarity", { name: movieTitle });
    if (response === "Sorry! The movie you requested is not in our database. Please check the spelling or try with some other movies") {
      $('.fail').css('display', 'block');
      $('.results').css('display', 'none');
      $("#loader").fadeOut();
    } else {
      const movieArray = response.split('---');
      await getMovieDetails(movieId, myApiKey, movieArray, movieTitle);
    }
  } catch (error) {
    console.error('Error fetching recommendations:', error);
    alert('Error fetching recommendations.');
    $("#loader").fadeOut();
  }
}

// Get detailed movie information
async function getMovieDetails(movieId, myApiKey, recommendations, movieTitle) {
  try {
    const response = await fetch(`https://api.themoviedb.org/3/movie/${movieId}?api_key=${myApiKey}`);
    const movieDetails = await response.json();

    const imdbId = movieDetails.imdb_id;
    const poster = `https://image.tmdb.org/t/p/original${movieDetails.poster_path}`;
    const overview = movieDetails.overview;
    const genres = movieDetails.genres.map(g => g.name).join(', ');
    const rating = movieDetails.vote_average;
    const voteCount = movieDetails.vote_count.toLocaleString();
    const releaseDate = new Date(movieDetails.release_date).toDateString().split(' ').slice(1).join(' ');
    const runtime = formatRuntime(movieDetails.runtime);
    const status = movieDetails.status;

    const posters = await getMoviePosters(recommendations, myApiKey);
    const cast = await getMovieCast(movieId, myApiKey);
    const individualCastDetails = await getIndividualCast(cast, myApiKey);

    const details = {
      title: movieTitle,
      cast_ids: JSON.stringify(cast.map(c => c.id)),
      cast_names: JSON.stringify(cast.map(c => c.name)),
      cast_chars: JSON.stringify(cast.map(c => c.character)),
      cast_profiles: JSON.stringify(cast.map(c => c.profile)),
      cast_bdays: JSON.stringify(individualCastDetails.bdays),
      cast_bios: JSON.stringify(individualCastDetails.bios),
      cast_places: JSON.stringify(individualCastDetails.places),
      imdb_id: imdbId,
      poster: poster,
      genres: genres,
      overview: overview,
      rating: rating,
      vote_count: voteCount,
      release_date: releaseDate,
      runtime: runtime,
      status: status,
      rec_movies: JSON.stringify(recommendations),
      rec_posters: JSON.stringify(posters),
    };

    await $.post("/recommend", details, function (response) {
      $('.results').html(response);
      $('#autoComplete').val('');
      $(window).scrollTop(0);
    });
    $("#loader").fadeOut();
  } catch (error) {
    console.error('Error fetching movie details:', error);
    alert('Error fetching movie details.');
    $("#loader").fadeOut();
  }
}

// Format runtime in hours and minutes
function formatRuntime(runtime) {
  if (runtime % 60 === 0) {
    return `${Math.floor(runtime / 60)} hour(s)`;
  }
  return `${Math.floor(runtime / 60)} hour(s) ${runtime % 60} min(s)`;
}

// Fetch movie posters for recommendations
async function getMoviePosters(movieTitles, myApiKey) {
  const posterPromises = movieTitles.map(async (title) => {
    try {
      const response = await fetch(`https://api.themoviedb.org/3/search/movie?api_key=${myApiKey}&query=${title}`);
      const movie = await response.json();
      return `https://image.tmdb.org/t/p/original${movie.results[0].poster_path}`;
    } catch (error) {
      console.error(`Error fetching poster for ${title}:`, error);
      return null;
    }
  });

  return Promise.all(posterPromises);
}

// Fetch cast information for the movie
async function getMovieCast(movieId, myApiKey) {
  try {
    const response = await fetch(`https://api.themoviedb.org/3/movie/${movieId}/credits?api_key=${myApiKey}`);
    const credits = await response.json();

    return credits.cast.slice(0, 10).map(cast => ({
      id: cast.id,
      name: cast.name,
      character: cast.character,
      profile: `https://image.tmdb.org/t/p/original${cast.profile_path}`
    }));
  } catch (error) {
    console.error('Error fetching movie cast:', error);
    return [];
  }
}

// Fetch additional details for individual cast members
async function getIndividualCast(cast, myApiKey) {
  const castDetails = cast.map(async (member) => {
    try {
      const response = await fetch(`https://api.themoviedb.org/3/person/${member.id}?api_key=${myApiKey}`);
      const details = await response.json();

      return {
        bday: details.birthday ? new Date(details.birthday).toDateString().split(' ').slice(1).join(' ') : 'N/A',
        bio: details.biography || 'Biography not available.',
        place: details.place_of_birth || 'Place not available.'
      };
    } catch (error) {
      console.error(`Error fetching details for cast ID ${member.id}:`, error);
      return { bday: 'N/A', bio: 'N/A', place: 'N/A' };
    }
  });

  const resolved = await Promise.all(castDetails);
  return {
    bdays: resolved.map(c => c.bday),
    bios: resolved.map(c => c.bio),
    places: resolved.map(c => c.place)
  };
}
